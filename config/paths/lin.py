# coding=utf-8
# diese Pfade bitte nicht ändern, sondern in der user.py überschreiben,
# da diese Datei bei Updates überschrieben wird
from os.path import expanduser, join
git = "/usr/bin/git"
ssh = "/usr/bin/ssh"
java = "/usr/bin/java"
jameica_cmd = ["/usr/bin/jameica"]
jameica_cwd = None
jameica_properties = join(expanduser("~"), ".jameica.properties")