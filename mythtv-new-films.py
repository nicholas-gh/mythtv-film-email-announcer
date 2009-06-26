#!/usr/bin/python


import os
import ConfigParser
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import MySQLdb
from MySQLdb.cursors import DictCursor
from imdb import IMDb
from genshi.template import MarkupTemplate, TemplateLoader
import sys
import smtplib

config = ConfigParser.SafeConfigParser()

config_file = os.path.expanduser('~/.mythtv_films_announcer_rc')
if os.path.exists(config_file):
    config.read(config_file)
else:
    default_content = """[mythweb]
url = http://tv.example.com/mythweb

[imdb]
url = http://www.imdb.com

[db]
password  = 
host      = mythone
db        = mythconverg
host      = mythone
user      = mythtv
max_films = 200

[templates]
dir = /usr/local/share/mythtv-films-announcer
html = films-on-tv.html

[mail]
to = you@example.com
from = you@example.com
subject = Weekly New Films
host = mail.example.com
user = 
password = 
"""
    open(config_file, "w").write(default_content)
    print "Please edit %s and try again." % config_file
    sys.exit(2)

loader = TemplateLoader([config.get('templates','dir')])
html_template = loader.load(config.get('templates','html'))

db=MySQLdb.connect(passwd=config.get('db','password'),
                   db=config.get('db','db'),
                   host=config.get('db','host'),                   
                   user=config.get('db','user'),
                   cursorclass = DictCursor)
c = db.cursor()

ia = IMDb(accessSystem='http')

c.execute("""
SELECT count(title) as showings,
       chanid,
       title,
       description,
       min(starttime) as firstshowing,
       max(stars) as stars,
       airdate
from program
where category = "Film"
and starttime > now() and endtime <= ADDDATE(now(), 7)
group by title order by max(stars) desc limit %s""" % config.get('db','max_films'))
shows = []
results = c.fetchall()
for show in results:
    show['mythweb_url'] = "%s/tv/detail/%s/%s" % (config.get('mythweb','url'),
                                                  show['chanid'], show['firstshowing'].strftime("%s"))
    for imdbresult in ia.search_movie(show['title'], results=5):
        imdbmovie = ia.get_movie(imdbresult.movieID)
        if abs(imdbmovie['year'] -  show['airdate']) < 2:
            show['imdb'] = imdbmovie
            show['imdb_url'] = "%s/title/tt%s/" % (config.get('imdb','url'),
                                                   imdbmovie.movieID)
            break
    shows.append(show)
    print "%s/%s" % (len(shows), len(results))
stream = html_template.generate(shows=shows)

msgRoot = MIMEMultipart('related')
msgRoot['Subject'] = config.get('mail','subject')
msgRoot['From']    = config.get('mail','from')
msgRoot['To']      = config.get('mail','to')
msgRoot.preamble = 'This is a multi-part message in MIME format.'

msgAlternative = MIMEMultipart('alternative')
msgRoot.attach(msgAlternative)

html_body = stream.render('xhtml')
msgText   = MIMEText(html_body, "html","UTF-8")
msgAlternative.attach(msgText)

smtp = smtplib.SMTP()
smtp.connect(config.get('mail','host'))
smtp.login(config.get('mail','user'),
           config.get('mail','password'))
smtp.sendmail(msgRoot['From'],
              [s.strip() for s in msgRoot['To'].split(",")],
              msgRoot.as_string())
smtp.quit()

if False:
    import webbrowser
    t = "/tmp/output.xhtml"
    open(t,"w").write(html_body)
    webbrowser.open(t)
