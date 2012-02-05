import tornado
import sys
sys.path.append('../')
from ape import ApeHandler

class ApeMove(ApeHandler):
    def cmd_setpos(self, cmd, params):
        self.session.properties['x'] = params['x']
        self.session.properties['y'] = params['y']

        chan = self.get_channel("move")
        not_to = set([self.session])
        chan.send_raw('positions', data={"x":params['x'], "y":params['y'], "from":self.session.get_pipe_info()}, not_to=not_to);

    def cmd_send(self, cmd, params):
        message = params['msg']
        chan = self.get_channel("move")
        chan.send_raw('DATA', data={"msg":message, "from":self.session.get_pipe_info()}, not_to=set([self.session]))


if __name__ == "__main__":
    application = tornado.web.Application([
        (r'/', ApeMove),
        (r'/0/', ApeMove),
    ])
    application.listen(6969)
    tornado.ioloop.IOLoop.instance().start()
