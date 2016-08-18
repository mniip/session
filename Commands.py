from Reload import reloadable
import Irc, Config
import imp, sys, traceback, subprocess

@reloadable
class CommandHandler(Irc.Client):
    handlers = dict(Irc.Client.handlers)

@CommandHandler.hook(b"001")
def welcome(self, msg):
    for channel in self.conf["channels"]:
        self.send(Irc.Message(b"JOIN", channel))
    if "password" in self.conf:
        self.send(Irc.Message(b"NS", b"IDENTIFY " + Irc.encode(self.conf["password"])))

commands = {}

def command(cmd):
    def decorator(fun):
        commands[cmd] = fun
        return fun
    return decorator

def admin_only(fun):
    def check_admin(request):
        if request.msg.source.is_admin():
            return fun(request)
    return check_admin

class Request:
    def __init__(self, conn, context, msg, command, args):
        self.conn = conn
        self.context = context
        self.msg = msg
        self.command = command
        self.args = args

    def say(self, text):
        while len(text) > 300:
            self.conn.send(Irc.Message("PRIVMSG", self.context, text[:300]))
            text = text[300:]
        self.conn.send(Irc.Message("PRIVMSG", self.context, text))

    def reply(self, text):
        text = Irc.encode(text)
        while len(text) > 300:
            self.conn.send(Irc.Message("PRIVMSG", self.context, self.msg.source.nick + b": " + text[:300]))
            text = text[300:]
        self.conn.send(Irc.Message("PRIVMSG", self.context, self.msg.source.nick + b": " + text))

@CommandHandler.hook(b"PRIVMSG")
def privmsg(self, msg):
    query = msg.arguments[1].decode("utf_8", "replace")
    for trigger, conf in Config.config["triggers"].items():
        text = query
        if "beginswith" in conf:
            expected = conf["beginswith"]
            prefix = text[:len(expected)]
            text = text[len(expected):]
            if prefix != expected:
                continue
        if "endswith" in conf:
            expected = conf["endswith"]
            suffix = text[-len(expected):]
            text = text[:-len(expected)]
            if suffix != expected:
                continue
        if "command" in conf:
            command = conf["command"]
            args = text.split(" ")
        else:
            command, *args = text.split(" ")
        if command not in commands:
            continue
        if msg.arguments[0] == self.nickname:
            context = msg.source.nick
        else:
            context = msg.arguments[0]
        request = Request(self, context, msg, command, args)
        try:
            commands[command](request)
        except Exception:
            type, value, tb = sys.exc_info()
            err = traceback.format_exception(type, value, tb)
            del tb
            request.say(b" ".join(Irc.encode(e.rstrip("\n")) for e in err))
        break

@command("echo")
def echo(request):
    request.reply(" ".join(request.args))

@command("raise")
def raise_(request):
    raise RuntimeError(" ".join(request.args))

@command("moo")
def moo(request):
    request.say("moo")

@command("reload")
@admin_only
def reload(request):
    for module in request.args:
        imp.reload(sys.modules[module])
    request.reply("Done")

@command("eval")
@admin_only
def eval_(request):
    try:
        result = eval(" ".join(request.args))
        if result is not None:
            request.say(b" " + Irc.encode(repr(result)))
    except SyntaxError:
        exec(" ".join(request.args))

@command("raw")
@admin_only
def raw(request):
    request.conn.raw_write(Irc.encode(" ".join(request.args)) + b"\r\n")

@command("shell")
@admin_only
def shell(request):
    args = request.args
    vertical = False
    if request.command == "shell" and args[0] == "--vertical":
        args = args[1:]
        vertical = True
    proc = subprocess.Popen(["script", "-q", "/dev/null", "-c", "TERM=ansi bash -ic '" + " ".join(args).replace("'", "'\\''") + "'"], stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    try:
        outs, errs = proc.communicate(b"", timeout = 60)
        ircize = subprocess.Popen(["../ircize", "--remove"], stdin = subprocess.PIPE, stdout = subprocess.PIPE)
        outs, errs = ircize.communicate(outs)
        lines = outs.split(b"\n")
        if vertical:
            for line in lines:
                while len(line) > 250:
                    request.say(b" " + line[:250])
                request.say(b" " + line)
        else:
            accum = b""
            for line in lines:
                if len(line):
                    if len(line) + 2 + len(accum) > 250:
                        request.say(b" " + accum)
                        accum = line
                    else:
                        if len(accum):
                            accum += b"; " + line
                        else:
                            accum = line
                        while len(accum) > 250:
                            request.say(b" " + accum[:250])
                            accum = accum[250:]
            request.say(b" " + accum)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        request.reply("Timed out")
        pass

@command("highlight")
def shell(request):
    if len(request.args):
        lang = request.args[0]
        code = " ".join(request.args[1:])
        proc = subprocess.Popen(["source-highlight", "--style", "ansi.style", "-q", "-f", "ansi", "-s", lang], stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        outs, errs = proc.communicate(Irc.encode(code))
        if not len(errs):
            ircize = subprocess.Popen(["../ircize", "--remove"], stdin = subprocess.PIPE, stdout = subprocess.PIPE)
            outs, errs = ircize.communicate(outs)
            request.reply(outs)

@command("list")
def list_(request):
    cmds = {}
    for cmd, fun in commands.items():
        fun = id(fun)
        if fun not in cmds:
            cmds[fun] = []
        cmds[fun].append(cmd)
    for trigger, conf in Config.config["triggers"].items():
        if "command" in conf:
            if conf["command"] in commands:
                fun = id(commands[conf["command"]])
                cmds[fun].append(conf.get("beginswith", "") + "\x02...\x02" + conf.get("endswith", ""))
    request.reply(", ".join(sorted(" \x02/\x02 ".join(names) for names in cmds.values())))

@command("message")
def message(request):
    request.reply(repr(request.msg))
