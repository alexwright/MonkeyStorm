import base64
import hashlib
import random
import json
import urllib2

import tornado.ioloop
import tornado.web

import time

def gen_token():
    rand_str = str(random.getrandbits(128))
    return hashlib.md5(rand_str).hexdigest()

sessions = dict()
class ApeSession:
    def __init__(self):
        self.token = gen_token()
        self.pubid = gen_token()
        self.properties = dict()
        self.requests = set()

        sessions[self.token] = self

    def remove_request(self, request):
        if request in self.requests:
            self.requests.remove(request)

    def add_request(self, request):
        self.requests.add(request)

channels = dict()
class ApeChannel:
    def __init__(self, name):
        self.name = name
        self.token = gen_token()
        self.subs = set()

    def join(self, session):
        self.subs.add(session)

    def part(self, session):
        if session in self.subs:
            self.subs.remove(session)

class ApeHandler(tornado.web.RequestHandler):
    def get(self):
        qs = urllib2.unquote(self.request.query)
        qs = json.loads(qs)
        self.handle(qs)

    @tornado.web.asynchronous
    def post(self):
        self.payload = []

        body = json.loads(urllib2.unquote(self.request.body))
        self.handle(body)

        if len(self.payload) > 0:
            self.send(self.payload)

    def send(self, messages):
        if self.session:
            self.session.remove_request(self)

        self.set_status(200)
        self.write(json.dumps(messages))
        self.finish()

    def send_close(self):
        close = self.response(raw="CLOSE", data={})
        self.payload.append(close)
        self.send(self.payload)

    def close(self):
        # Some times the client has disconnected and this will raise IO Error
        try:
            self.finish()
        except IOError:
            pass

    def handle(self, commands):
        for command in commands:
            if "sessid" in command:
                if not self.long_poll(command['sessid']):
                    self.set_status(400)
                    self.write('Session not found')
                    self.close()
                    return
                del command['sessid']

        for command in commands:
            self.command(command)
    
    def command(self, command):
        print "Command: " + str(command)
        if not command['cmd']:
            self.set_status(400)
            return

        cmd_name = 'cmd_' + command['cmd'].lower()
        if cmd_name not in dir(self):
            self.not_found(command)
            self.set_status(404)
            return

        method = getattr(self, cmd_name)
        if not callable(method):
            self.set_status(403)
            return
        
        # not sure what chl is even for
        if "chl" in command:
            del command["chl"]

        method(**command)

    def long_poll(self, sessid):
        if sessid not in sessions:
            return False
            #raise tornado.web.HTTPError(400, "Session Not Found")

        self.session = sessions[sessid]

        # This request will become the active long-poll request for the session. Replace any others.
        for request in self.session.requests.copy():
            request.send_close()
        self.session.add_request(self)
        return True
    
    def not_found(self, command):
        print "No hander found for cmd '" + command['cmd'] + "'. Params: " + str(command)

    def time(self):
        return int(time.time())

    def response(self, **kwargs):
        kwargs['time'] = self.time()
        return kwargs

    def cmd_script(self, cmd, params):
        self.write('<html><head></head><body>')
        self.write('<script type="text/javascript">document.domain="' + params['domain'] + '";</script>')
        for url in params['scripts']:
            self.write('<script type="text/javascript" src="' + url + '"></script>')

        self.write('</body></html>')

    def cmd_connect(self, cmd, params):
        s = self.session = ApeSession()
        
        if "name" in params:
            s.properties['name'] = params['name']

        login = self.response(raw="LOGIN", data={"sessid":s.token})
        self.payload.append(login)

        user = {"user":{"casttype":"uni", "pubid":s.pubid, "properties":s.properties}}
        ident = self.response(raw="IDENT", data=user)
        self.payload.append(ident)

    def cmd_check(self, cmd):
        print "chk: {0}".format(self.session.token)

    def get_channel(self, chan_name):
        if chan_name in channels:
            return channels[chan_name]
        else:
            return ApeChannel(chan_name)
        
    def cmd_join(self, cmd, params):
        # 'channels' can be 'chan_name', ['chan_name'], or ['chan_1', 'chan_2']
        if params['channels'] == str(params['channels']):
            params['channels'] = [params['channels']]

        for chan_name in params['channels']:
            chan = self.get_channel(chan_name)
            chan.join(self.session)
            pipe = {"casttype":"multi", "pubid":chan.token, "properties":{ "name":chan.name }}
            users = []
            for s in chan.subs:
                users.append({ "casttype":"uni", "pubid":s.pubid, "properties":s.properties })

            join = self.response(raw="CHANNEL", data={"pipe":pipe, "users":users })
            self.payload.append(join)

            print "Joining: " + chan_name

        print "Join: " + str(params)

application = tornado.web.Application([
    (r'/', ApeHandler),
    (r'/0/', ApeHandler),
])

if __name__ == "__main__":
    print "Starting."
    application.listen(6969)
    tornado.ioloop.IOLoop.instance().start()
