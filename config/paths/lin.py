# coding=utf-8
# diese Pfade bitte nicht ändern, sondern in der user.py überschreiben,
# da diese Datei bei Updates überschrieben wird
from os.path import expanduser, join
rsync = "/usr/bin/rsync"
git = "/usr/bin/git"
ssh = "/usr/bin/ssh"
mysql = "/usr/bin/mysql"
mysqldump = "/usr/bin/mysqldump"
jameica_cmd = ["/usr/bin/jameica"]
jameica_cwd = None
jameica_properties = join(expanduser("~"), ".jameica.properties")