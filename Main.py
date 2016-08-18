import Config, Irc, Commands

conn = Commands.CommandHandler(list(Config.config["connections"].values())[0])
conn.connect()
conn.register()

for msg in conn.traverse():
    pass
