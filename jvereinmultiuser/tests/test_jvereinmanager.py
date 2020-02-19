import os
import shutil
import logging
import textwrap
import subprocess
from unittest import TestCase
from tempfile import TemporaryDirectory

from jvereinmultiuser.jvereinmanager import JVereinManager

JAVA_PATH = "/Applications/jameica2.8.6.app/jre-macos64/Contents/Home/bin/java"
H2_PATH = "/Applications/jameica2.8.6.app/lib/h2/h2-1.4.199.jar"

EXAMPLE_JVEREIN_DATABASE = textwrap.dedent("""\
    CREATE USER IF NOT EXISTS "JVEREIN" SALT 'b639d0d2ad3657a9' HASH '12091ed2f3d5c62f8b4297da36ca4fad7db9ff51a6844da8b95bddd0fb4e2ad5' ADMIN;
    
    CREATE CACHED TABLE "PUBLIC"."MITGLIED"(
        "ID" BIGINT NOT NULL,
        "EXTERNEMITGLIEDSNUMMER" VARCHAR(50),
        "ADRESSTYP" BIGINT NOT NULL,
        "PERSONENART" CHAR(1),
        "ANREDE" VARCHAR(40),
        "TITEL" VARCHAR(40),
        "NAME" VARCHAR(40) NOT NULL,
        "VORNAME" VARCHAR(40),
        "ADRESSIERUNGSZUSATZ" VARCHAR(40),
        "STRASSE" VARCHAR(40) NOT NULL,
        "PLZ" VARCHAR(10) NOT NULL,
        "ORT" VARCHAR(40) NOT NULL,
        "STAAT" VARCHAR(50),
        "ZAHLUNGSWEG" INTEGER,
        "ZAHLUNGSRHYTMUS" INTEGER,
        "MANDATDATUM" DATE,
        "MANDATVERSION" INTEGER,
        "MANDATSEQUENCE" VARCHAR(4),
        "BIC" VARCHAR(11),
        "IBAN" VARCHAR(34),
        "KTOIPERSONENART" CHAR(1),
        "KTOIANREDE" VARCHAR(40),
        "KTOITITEL" VARCHAR(40),
        "KTOINAME" VARCHAR(40),
        "KTOIVORNAME" VARCHAR(40),
        "KTOISTRASSE" VARCHAR(40),
        "KTOIADRESSIERUNGSZUSATZ" VARCHAR(40),
        "KTOIPLZ" VARCHAR(10),
        "KTOIORT" VARCHAR(40),
        "KTOISTAAT" VARCHAR(50),
        "KTOIEMAIL" VARCHAR(255),
        "GEBURTSDATUM" DATE,
        "GESCHLECHT" CHAR(1),
        "TELEFONPRIVAT" VARCHAR(20),
        "TELEFONDIENSTLICH" VARCHAR(20),
        "HANDY" VARCHAR(20),
        "EMAIL" VARCHAR(255),
        "EINTRITT" DATE,
        "BEITRAGSGRUPPE" BIGINT,
        "INDIVIDUELLERBEITRAG" DOUBLE,
        "ZAHLERID" BIGINT,
        "AUSTRITT" DATE,
        "KUENDIGUNG" DATE,
        "STERBETAG" DATE,
        "VERMERK1" VARCHAR(2000),
        "VERMERK2" VARCHAR(2000),
        "EINGABEDATUM" DATE,
        "LETZTEAENDERUNG" DATE,
        "KTOIGESCHLECHT" VARCHAR(1),
        "ZAHLUNGSTERMIN" INTEGER
    );
    ALTER TABLE "PUBLIC"."MITGLIED" ADD CONSTRAINT "PUBLIC"."CONSTRAINT_E" PRIMARY KEY("ID");
    
    INSERT INTO "PUBLIC"."MITGLIED" VALUES
    (1, NULL, 1, 'n', '', '', 'Mustermann', 'Max', '', STRINGDECODE('Musterdorfer Straße 2'), '12345', 'Musterhausen', '', 2, 1, NULL, 1, 'FRST', '', '', 'n', '', '', '', '', '', '', '', '', '', '', NULL, 'm', '', '', '', 'mustermann@example.org', DATE '2020-01-01', 1, NULL, NULL, NULL, NULL, NULL, NULL, '', NULL, DATE '2020-01-01', 'm', NULL),
    (2, NULL, 1, 'n', '', '', 'Musterfrau', 'Anna', '', STRINGDECODE('Musterdorfer Straße 2'), '12345', 'Musterhausen', '', 2, 1, NULL, 1, 'FRST', '', '', 'n', '', '', '', '', '', '', '', '', '', '', NULL, 'w', '', '', '', 'musterfrau@example.org', DATE '2020-01-01', 1, NULL, NULL, NULL, NULL, NULL, NULL, '', NULL, DATE '2020-01-01', 'm', NULL);
""")


# noinspection DuplicatedCode
class TestJVereinManager(TestCase):

    def setUp(self) -> None:
        super().setUp()
        logging.basicConfig(format="[%(asctime)s] %(levelname)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                            level=logging.DEBUG)

    def _set_up_example_database(self, jdbc_path):
        try:
            os.makedirs(os.path.dirname(jdbc_path))
        except FileExistsError:
            pass

        temp_file_path = f"{jdbc_path}.sql"
        with open(temp_file_path, "w") as f:
            f.write(EXAMPLE_JVEREIN_DATABASE)

        subprocess.run([JAVA_PATH,
                        "-cp", H2_PATH,
                        "org.h2.tools.RunScript",
                        "-url", f"jdbc:h2:{jdbc_path}",
                        "-user", "jverein",
                        "-password", "jverein",
                        "-script", temp_file_path])

    def test__insert_user_properties_into_properties_files(self):
        with TemporaryDirectory() as tmp_dir:
            src_dir = os.path.join(os.path.dirname(__file__), "test_jvereinmanager_working_dir")
            repo_dir = os.path.join(tmp_dir, "repo_dir")
            shutil.copytree(src_dir, repo_dir)

            user_properties = {
                "cfg/de.willuhn.jameica.gui.GUI.properties": {
                    "main.width.0": "100",
                    "snapin.height.1": "101",
                    "snapin.height.0": "102",
                    "window.maximized": "false",
                    "main.width.1": "103",
                    "window.width": "104",
                    "navi.height.1": "105",
                    "navi.height.0": "106",
                    "window.height": "107",
                    "window.x": "108",
                    "window.y": "109",
                }
            }

            gui_properties_with_user_properties = textwrap.dedent("""\
                #Fri Feb 14 21:26:33 CET 2020
                main.width.0=100
                snapin.height.1=101
                snapin.height.0=102
                window.maximized=false
                main.width.1=103
                window.width=104
                navi.height.1=105
                navi.height.0=106
                window.height=107
                window.x=108
                window.y=109
            """).strip()

            j = JVereinManager(repo_dir, user_properties, JAVA_PATH, H2_PATH)
            j._insert_user_properties_into_properties_files()

            gui_file = os.path.join(repo_dir, "jameica", "cfg", "de.willuhn.jameica.gui.GUI.properties")
            with open(gui_file, "r") as f:
                modified_content = f.read().strip()
                self.assertEqual(gui_properties_with_user_properties, modified_content)

    def test__reset_user_properties_in_properties_files(self):
        with TemporaryDirectory() as tmp_dir:
            src_dir = os.path.join(os.path.dirname(__file__), "test_jvereinmanager_working_dir")
            repo_dir = os.path.join(tmp_dir, "repo_dir")
            shutil.copytree(src_dir, repo_dir)

            user_properties = {
                "cfg/de.willuhn.jameica.gui.GUI.properties": {
                    "main.width.0": "100",
                    "snapin.height.1": "101",
                    "snapin.height.0": "102",
                    "window.maximized": "false",
                    "main.width.1": "103",
                    "window.width": "104",
                    "navi.height.1": "105",
                    "navi.height.0": "106",
                    "window.height": "107",
                    "window.x": "108",
                    "window.y": "109",
                }
            }

            expected_user_properties = {
                "cfg/de.willuhn.jameica.gui.GUI.properties": {
                    "main.width.0": "156",
                    "snapin.height.1": "229",
                    "snapin.height.0": "770",
                    "window.maximized": "true",
                    "main.width.1": "843",
                    "window.width": "1414",
                    "navi.height.1": "202",
                    "navi.height.0": "793",
                    "window.height": "877",
                    "window.x": "26",
                    "window.y": "45",
                }
            }

            expected_reset_gui_properties_content = textwrap.dedent("""\
                #Fri Feb 14 21:26:33 CET 2020
                main.width.0=
                snapin.height.1=
                snapin.height.0=
                window.maximized=
                main.width.1=
                window.width=
                navi.height.1=
                navi.height.0=
                window.height=
                window.x=
                window.y=
            """).strip()

            j = JVereinManager(repo_dir, user_properties, JAVA_PATH, H2_PATH)
            j._reset_user_properties_in_properties_files()

            gui_file = os.path.join(repo_dir, "jameica", "cfg", "de.willuhn.jameica.gui.GUI.properties")
            with open(gui_file, "r") as f:
                modified_content = f.read().strip()
                self.assertEqual(expected_reset_gui_properties_content, modified_content)

            self.assertEqual(expected_user_properties["cfg/de.willuhn.jameica.gui.GUI.properties"],
                             j.user_properties["cfg/de.willuhn.jameica.gui.GUI.properties"])

    def test__export_emails(self):
        with TemporaryDirectory() as tmp_dir:
            src_dir = os.path.join(os.path.dirname(__file__), "test_jvereinmanager_working_dir")
            repo_dir = os.path.join(tmp_dir, "repo_dir")
            shutil.copytree(src_dir, repo_dir)

            jdbc_path = os.path.join(repo_dir, "jameica", "jverein", "h2db", "jverein")
            self._set_up_example_database(jdbc_path)

            j = JVereinManager(repo_dir, {}, JAVA_PATH, H2_PATH)
            j._export_emails()

            expected_emails = textwrap.dedent("""\
                musterfrau@example.org
                mustermann@example.org
            """).strip()

            with open(os.path.join(repo_dir, "dump", "mitglieder-emails.csv")) as f:
                self.assertEqual(expected_emails, f.read().strip())

    def test__decrypt_passphrase_successful(self):
        encrypted_passphrase = "WmpFkXzBjV6B6ySu9cAH05GusKbdmoZdt+FvVnqP5RpwbP5pQD8nOZKujV7lTqtfrIwz08ASmAtk\r\nTCgJqvJsOE76W4lbUGSLgJWYbSK5W1svu93Ne1exRI6BHG8HvUXiocNpog7Uajuf+3hjn2kYYQLO\r\nnPZo29e8CP17ovqodcw3aKA5PaN4HH+jHR7WfUP/tgZrEBf0zgc9l0vkmLzA3bVVyu88SaY385jl\r\n4ASYWzxPY3xR2y81/MvPIEKio4YmWEUVur5fKYXupVg1ANp1GFK/bfS2hpK1jcm6zmKwR58kQfy1\r\nyMUCsIlhc7k48SFZoi1BQ+Aiza52qRdWtfzRzA\=\="
        master_password = "password"
        expected_decrypted_passphrase = "Kh3BdGN9haQVFS2eJLne4aBINbQ= Kh3BdGN9haQVFS2eJLne4aBINbQ="

        with TemporaryDirectory() as tmp_dir:
            src_dir = os.path.join(os.path.dirname(__file__), "test_jvereinmanager_working_dir")
            repo_dir = os.path.join(tmp_dir, "repo_dir")
            shutil.copytree(src_dir, repo_dir)

            j = JVereinManager(repo_dir, {}, JAVA_PATH, H2_PATH)
            decrypted_passphrase = j._decrypt_passphrase(encrypted_passphrase, master_password)
            self.assertEqual(expected_decrypted_passphrase, decrypted_passphrase)

    def test__decrypt_passphrase_missing_file(self):
        encrypted_passphrase = "WmpFkXzBjV6B6ySu9cAH05GusKbdmoZdt+FvVnqP5RpwbP5pQD8nOZKujV7lTqtfrIwz08ASmAtk\r\nTCgJqvJsOE76W4lbUGSLgJWYbSK5W1svu93Ne1exRI6BHG8HvUXiocNpog7Uajuf+3hjn2kYYQLO\r\nnPZo29e8CP17ovqodcw3aKA5PaN4HH+jHR7WfUP/tgZrEBf0zgc9l0vkmLzA3bVVyu88SaY385jl\r\n4ASYWzxPY3xR2y81/MvPIEKio4YmWEUVur5fKYXupVg1ANp1GFK/bfS2hpK1jcm6zmKwR58kQfy1\r\nyMUCsIlhc7k48SFZoi1BQ+Aiza52qRdWtfzRzA\=\="
        master_password = "password"

        with TemporaryDirectory() as tmp_dir:
            src_dir = os.path.join(os.path.dirname(__file__), "test_jvereinmanager_working_dir")
            repo_dir = os.path.join(tmp_dir, "repo_dir")
            shutil.copytree(src_dir, repo_dir)
            os.unlink(os.path.join(repo_dir, "jameica", "cfg", "jameica.keystore"))

            j = JVereinManager(repo_dir, {}, JAVA_PATH, H2_PATH)
            self.assertRaises(FileNotFoundError, j._decrypt_passphrase, encrypted_passphrase, master_password)