# coding=utf-8
# diese Pfade bitte nicht ändern, sondern in der user.py überschreiben,
# da diese Datei bei Updates überschrieben wird
from os.path import expanduser, join
rsync = "/usr/bin/rsync"
git = "/usr/bin/git"
ssh = "/usr/bin/ssh"
mysql = "/Applications/MySQLWorkbench.app/Contents/MacOS/mysql"
mysqldump = "/Applications/MySQLWorkbench.app/Contents/MacOS/mysqldump"
jameica_cmd = ["/Applications/jameica.app/jameica-macos64.sh"]
jameica_cwd = None
jameica_properties = join(expanduser("~"), ".jameica.properties")