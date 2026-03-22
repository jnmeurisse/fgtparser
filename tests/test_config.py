import io
import unittest
from pathlib import Path
from typing import cast

from src.fgtparser import (
    FgtConfigNode,
    FgtConfigObject,
    FgtConfigRoot,
    FgtConfigSet,
    FgtConfigTable,
    load,
    loads,
    uqs,
    qus,
)
from tests import make_test_path


class TestConfig(unittest.TestCase):
    @staticmethod
    def _same_config(cfg1: list[str], cfg2: list[str]) -> bool:
        # Compare line by line for equality.  Leading and trailing spaces are not significant.
        return all(line1.strip() == line2.strip() for line1, line2 in zip(cfg1, cfg2, strict=False))

    @staticmethod
    def _parse_and_compare(filename: Path, encoding: str = 'ascii') -> bool:
        # Load and parse the configuration file
        config = load(filename, encoding)

        # Write the configuration to a memory file
        output_buffer = io.StringIO()
        config.dump(output_buffer, True)

        # Split as a list of strings
        text_config_1 = output_buffer.getvalue().split("\n")

        # Do the same with the file
        with open(filename, encoding=encoding) as f:
            text_config_2 = f.read().split("\n")

        # and compare for equality
        return TestConfig._same_config(text_config_1, text_config_2)

    def test_config1(self) -> None:
        self.assertTrue(TestConfig._parse_and_compare(make_test_path("test1.conf")))

    def test_config2(self) -> None:
        self.assertTrue(TestConfig._parse_and_compare(make_test_path("test2.conf")))

    def test_config3(self) -> None:
        self.assertTrue(TestConfig._parse_and_compare(make_test_path("test3.conf")))

    def test_config4(self) -> None:
        self.assertTrue(TestConfig._parse_and_compare(make_test_path("test4.conf"), 'latin-1'))

    def test_factory(self) -> None:
        class RootConfig(FgtConfigRoot):
            def system_global(self) -> FgtConfigObject:
                return self.c_object('system global')

            def interface(self) -> FgtConfigTable:
                return self.c_table('system interface')

            def firewall_address6(self) -> FgtConfigTable:
                return self.c_table('firewall address6')

        config = load(make_test_path("test3.conf"), factory_fn=lambda cfg: RootConfig(cfg))
        config_root = cast(RootConfig, config.root)

        config_global = config_root.system_global()
        self.assertEqual("12", config_global.param("timezone"))
        self.assertEqual("12", config_global.timezone)

        config_address = config_root.firewall_address6()
        self.assertEqual(
            "::/128",
            config_address.c_entry('none').param('ip6')
        )
        self.assertEqual(
            "::/128",
            config_address.c_entry('none').ip6
        )

        config_interface = config_root.interface()
        self.assertEqual(
            FgtConfigSet(["10.1.1.10", "255.255.255.0"]),
            config_interface.c_entry('port1').ip
        )
        self.assertEqual(
            "ping",
            config_interface.c_entry('port5').allowaccess
        )

    def test_section(self) -> None:
        config = load(make_test_path("test3.conf"))
        config_root = config.root

        for key, _ in config_root.sections("router  bgp"):
            self.assertEqual("router bgp", key)

        section_count = 0
        for _, _ in config_root.sections('router'):
            section_count += 1
        self.assertEqual(8, section_count)

    def test_table(self) -> None:
        config = load(make_test_path("test3.conf"))
        config_root = config.root

        config_address = config_root.c_table("firewall address")
        dmz_address_1 = config_address.c_entry('DMZ')
        self.assertEqual(dmz_address_1.c_set('subnet'), FgtConfigSet(['172.16.1.0', '255.255.255.0']))
        dmz_address_2 = config_address['DMZ']
        self.assertEqual(dmz_address_2['subnet'], FgtConfigSet(['172.16.1.0', '255.255.255.0']))

    def test_walk(self) -> None:
        config = load(make_test_path("test3.conf"))
        config_root = config.root

        replace_messages_walk = []
        for key, node in config_root.walk('', ''):
            if key.startswith('system replacemsg mail'):
                replace_messages_walk.append(key)

        replace_messages_filter = []
        for key, node in config_root.sections('system replacemsg mail .*'):
            replace_messages_filter.append(key)

        self.assertEqual(replace_messages_walk, replace_messages_filter)

    def test_parse_section(self) -> None:
        config_string = """
            config test
                set vdom "root"
                set ip 192.168.254.99 255.255.255.0
                set allowaccess ping https
                set alias "mngt"
                config example
                end
            end
        """
        config = loads(config_string)
        config_test = config.root.c_object("test")
        self.assertIsInstance(config_test.example, FgtConfigNode)
        self.assertIsInstance(config_test.example, FgtConfigObject)
        self.assertEqual(len(config_test), 5)
        self.assertEqual(config_test.skeys(), ["alias", "allowaccess", "example", "ip", "vdom"])

        self.assertIsInstance(config_test.get('vdom'), FgtConfigSet)
        self.assertEqual(config_test.get('vdom'), '"root"')
        self.assertEqual(config_test.get('vdom'), FgtConfigSet(['"root"']))
        self.assertEqual(config_test.param('vdom'), '"root"')
        self.assertEqual(config_test.vdom, '"root"')

        self.assertIsInstance(config_test.c_object('example'), FgtConfigObject)
        self.assertEqual(len(config_test.example), 0)

    def test_parse_int_table(self) -> None:
        config_string = """
            config test
                edit 1
                    set param value
                next
                edit 2
                    set param value
                next
                edit 5
                    config xyz
                    end
                next
            end
        """
        config = loads(config_string)
        config_test = config.root.c_table("test")
        self.assertIsInstance(config_test, FgtConfigNode)
        self.assertIsInstance(config_test, FgtConfigTable)
        self.assertEqual(len(config_test), 3)
        self.assertEqual(config_test.skeys(), ["1", "2", "5"])
        self.assertIsInstance(config_test[1], FgtConfigObject)
        self.assertIsInstance(config_test[2], FgtConfigObject)
        self.assertIsInstance(config_test[5], FgtConfigObject)
        self.assertIsInstance(config_test.get("1"), FgtConfigObject)
        self.assertIsInstance(config_test.get("2"), FgtConfigObject)
        self.assertIsInstance(config_test.get("5"), FgtConfigObject)
        self.assertIsInstance(config_test.c_entry(1), FgtConfigObject)

    def test_encoding(self):
        config = load(make_test_path("test4.conf"), encoding='latin-1')
        config_root = config.root
        expected_comment = FgtConfigSet(['"Utilisateur avancé"'])
        self.assertEqual(uqs(config_root.c_table("user local").c_entry('André').comment), expected_comment)

    def test_default(self):
        config_string = """
            config test
            end
        """
        config = loads(config_string)
        config_test = config.root.c_object("test")
        self.assertEqual(config_test.param('item1'), None)
        self.assertEqual(config_test.param('item1', 'default'), 'default')

    def test_comparison(self):
        config = load(make_test_path("test4.conf"), encoding='latin-1')

        config_global = config.root.c_object('system global')
        self.assertEqual(config_global.c_set('alias'), '"FGT-HQ"')
        self.assertEqual('"FGT-HQ"', config_global.c_set('alias'))
        self.assertEqual(config_global.c_set('alias'), FgtConfigSet(['"FGT-HQ"']))
        self.assertEqual(FgtConfigSet(['"FGT-HQ"']), config_global.c_set('alias'))

        config_interface = config.root.c_table('system interface')
        config_port = config_interface['port1']
        allowed_access = FgtConfigSet(['ping', 'https', 'ssh',  'http', 'fgfm'])
        self.assertEqual(config_port.c_set('allowaccess'), allowed_access)
        self.assertEqual(allowed_access, config_port.c_set('allowaccess'))

        self.assertEqual(config_port.allowaccess, allowed_access)
        self.assertEqual(allowed_access, config_port.allowaccess)

    def test_get_attr(self):
        config = load(make_test_path("test4.conf"), encoding='latin-1')
        config_global = config.root.c_object('system global')
        self.assertEqual(config_global.alias, '"FGT-HQ"')

        with self.assertRaises(AttributeError):
            print(config_global.xxx)

        with self.assertRaises(AttributeError):
            print(config_global.len)

    def test_qs(self):
        self.assertEqual(qus('hello'), '"hello"')
        self.assertEqual(qus('say "hi"'), '"say \\"hi\\""')
        self.assertEqual(qus('back\\slash'), '"back\\\\slash"')
        self.assertEqual(qus('a\\"b'), '"a\\\\\\\"b"')

    def test_uqs(self):
        self.assertEqual('hello', uqs('"hello"'))
        self.assertEqual('say "hi"', uqs('"say \\"hi\\""'))
        self.assertEqual('back\\slash', uqs('"back\\\\slash"'))
        self.assertEqual('a\\"b', uqs('"a\\\\\\\"b"'))
