from Reload import reloadable
import State
import Config

import socket, select, random, time

def encode(value):
    if isinstance(value, str):
        return bytes(value, "utf_8")
    else:
        return value

@reloadable
class Source:
    def __init__(self, nick = None, user = None, host = None):
        self.nick = encode(nick)
        self.user = encode(user)
        self.host = encode(host)

    def __repr__(self):
        return "Source(%s%s)" % (self.nick, ", %s, %s" % (self.user, self.host) if self.host != None else "")

    @staticmethod
    def parse(src):
        if b"!" in src:
            nick, rest = src.split(b"!", 1)
            if b"@" in src:
                user, host = rest.split(b"@", 1)
            else:
                user = rest
                host = None
        else:
            user = None
            if b"@" in src:
                nick, host = src.split(b"@", 1)
            else:
                nick = src
                host = None
        return Source(nick, user, host)

    def serialize(self):
        if self.user == None:
            if self.host == None:
                return bytes(self.nick)
            else:
                return self.nick + b"@" + self.host
        else:
            if self.host == None:
                return self.nick + b"!" + self.user
            else:
                return self.nick + b"!" + self.user + b"@" + self.host

    def is_admin(self):
        return self.host in (encode(host) for host in Config.config["admins"])

@reloadable
class Message:
    def __init__(self, command, *arguments, source = Source(), tags = {}):
        self.command = encode(command)
        self.arguments = [encode(arg) for arg in arguments]
        self.source = source
        self.tags = {encode(key): encode(value) for key, value in tags.items()}

    def __repr__(self):
        return "Message(%s, %s%s%s)" % (repr(self.command), repr(self.arguments), ", tags=%s" % repr(self.tags) if len(self.tags) else "", ", source=%s" % repr(self.source) if self.source.nick != None else "")

    @staticmethod
    def parse(line):
        line = line.rstrip(b"\r\n")
        tags = {}
        if len(line) and line[0] == ord('@'):
            ret = line[1:].split(b" ", 1)
            for tag in ret[0].split(b";"):
                if ord('=') in tag:
                    key, value = tag.split(b"=", 1)
                    tags[key] = value.replace(b"\\\\", b"\\").replace(b"\\:", b";").replace(b"\\s", b" ").replace(b"\\r", b"\r").replace(b"\\n", b"\n")
                else:
                    tags[tag] = None
            line = ret[1] if len(ret) > 1 else b""
        if len(line) and line[0] == ord(':'):
            ret = line[1:].split(b" ", 1)
            source = Source.parse(ret[0])
            line = ret[1] if len(ret) > 1 else b""
        else:
            source = Source()
        ret = line.split(b" ", 1)
        command = ret[0]
        line = ret[1] if len(ret) > 1 else b""
        args = []
        while len(line):
            if line[0] == ord(':'):
                args.append(line[1:])
                break
            else:
                ret = line.split(b" ", 1)
                args.append(ret[0])
                if len(ret) > 1:
                    line = ret[1]
                else:
                    break
        return Message(command, *args, source = source, tags = tags)
    
    def serialize(self):
        args = list(self.arguments)
        if len(args):
            args[-1] = b":" + args[-1]
        line = b" ".join([self.command.replace(b"\r", b"").replace(b"\n", b"")] + [arg.replace(b"\r", b"").replace(b"\n", b"") for arg in args])
        if self.source.nick != None:
            line = b":" + self.source.serialize() + b" " + line
        if len(self.tags):
            tags = dict(self.tags)
            for tag in tags:
                if tags[tag] != None:
                    tags[tag] = tags[tag].replace(b"\\", b"\\\\").replace(b";", b"\\:").replace(b" ", b"\\s").replace(b"\r", b"\\r").replace(b"\n", b"\\n")
            line = b"@" + b";".join(key + b"=" + value if value != None else key for key, value in tags.items()) + b" " + line
        return line + b"\r\n"

@reloadable
class Connection(State.State):
    def __init__(self, conf):
        self.conf = conf
        self.last_send = time.time()
        self.buffer = b""
        self.set_state("disconnected")

    @State.equals("disconnected")
    def connect(self):
        hosts = socket.getaddrinfo(self.conf["host"], self.conf.get("port", 6667), socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        print(hosts)
        family, socktype, proto, canonname, sockaddr = random.choice(hosts)
        print(family, socktype, proto, canonname, sockaddr)
        self.socket = socket.socket(family, socktype, proto)
        self.socket.connect(sockaddr)
        self.set_state("connected")

    @State.isnt("disconnected")
    def raw_write(self, string):
        try:
            while len(string):
                size = self.socket.send(string)
                string = string[size:]
        except socket.error:
            self.set_state("disconnected")
            raise

    @State.isnt("disconnected")
    def send(self, msg):
        print(msg)
        self.raw_write(msg.serialize())

    @State.isnt("disconnected")
    def traverse(self):
        while True:
            while self.buffer.find(b"\n") != -1:
                line, self.buffer = self.buffer.split(b"\n", 1)
                line = line.rstrip(b"\r")
                yield Message.parse(line)
            try:
                self.buffer += self.socket.recv(4096)
            except socket.error:
                self.set_state("disconnected")
                raise

@reloadable
class Client(Connection):
    def __init__(self, conf):
        Connection.__init__(self, conf)
        self.nickname = None

    def throttle(self):
        delay = self.conf.get("throttle", 0.5) - (time.time() - self.last_send)
        if delay > 0:
            time.sleep(delay)
        self.last_send = time.time()

    def raw_send(self, msg):
        self.throttle()
        Connection.send(self, msg)

    @State.equals("established")
    def send(self, msg):
        self.raw_send(msg)

    handlers = {}
    
    @classmethod
    def hook(cls, word):
        def decorator(fun):
            if word in cls.handlers:
                cls.handlers[word] = cls.handlers[word] + [fun]
            else:
                cls.handlers[word] = [fun]
        return decorator

    @State.isnt("disconnected")
    def handle(self, msg):
        if msg.command in self.handlers:
            for handler in self.handlers[msg.command]:
                handler(self, msg)

    @State.equals("connected")
    def register(self):
        self.raw_send(Message(b"NICK", self.conf["nickname"]))
        self.nickname = encode(self.conf["nickname"])
        self.raw_send(Message(b"USER", self.conf.get("ident", self.conf["nickname"]), "*", self.conf["host"], self.conf.get("realname", self.conf["nickname"])))

    def traverse(self):
        for msg in Connection.traverse(self):
            print(msg)
            self.handle(msg)
            yield msg

@Client.hook(b"PING")
def ping(self, msg):
    self.raw_send(Message(b"PONG", *msg.arguments))

@Client.hook(b"001")
def welcome(self, msg):
    self.set_state("established")

@Client.hook(b"NICK")
def nick(self, msg):
    if msg.source.nick == self.nickname:
        self.nickname = msg.arguments[0]

