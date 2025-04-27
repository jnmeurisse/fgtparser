import io
import unittest
from pathlib import Path
from typing import cast

from fgtparser import FgtConfigRoot, FgtConfigTable, FgtConfigObject, FgtConfigNode, FgtConfigSet
from fgtparser import parse_file, parse_string, set_root_config_factory
from tests import make_test_path


class TestConfig(unittest.TestCase):
    @staticmethod
    def _same_config(cfg1: list[str], cfg2: list[str]) -> bool:
        # Compare line by line for equality.  Leading and trailing spaces are not significant.
        return all(line1.strip() == line2.strip() for line1, line2 in zip(cfg1, cfg2))

    @staticmethod
    def _parse_and_compare(filename: Path) -> bool:
        # Load and parse the configuration file
        config = parse_file(filename)

        # Write the configuration to a memory file
        output_buffer = io.StringIO()
        config.write(output_buffer, True)

        # Split as a list of strings
        text_config_1 = output_buffer.getvalue().split("\n")

        # Do the same with the file
        with open(filename, "r") as f:
            text_config_2 = f.read().split("\n")

        # and compare for equality
        return TestConfig._same_config(text_config_1, text_config_2)

    def test_config1(self) -> None:
        self.assertTrue(TestConfig._parse_and_compare(make_test_path("test1.conf")))

    def test_config2(self) -> None:
        self.assertTrue(TestConfig._parse_and_compare(make_test_path("test2.conf")))

    def test_config3(self) -> None:
        self.assertTrue(TestConfig._parse_and_compare(make_test_path("test3.conf")))

    def test_factory(self) -> None:
        class RootConfig(FgtConfigRoot):
            def system_global(self) -> FgtConfigObject:
                return self.c_object('system global')

            def interface(self) -> FgtConfigTable:
                return self.c_table('system interface')

            def firewall_address6(self) -> FgtConfigTable:
                return self.c_table('firewall address6')

        set_root_config_factory(lambda _, cfg: RootConfig(cfg))

        config = parse_file(make_test_path("test3.conf"))
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
            ["10.1.1.10", "255.255.255.0"],
            config_interface.c_entry('port1').ip
        )
        self.assertEqual(
            "ping",
            config_interface.c_entry('port5').allowaccess
        )

    def test_section(self) -> None:
        config = parse_file(make_test_path("test3.conf"))
        config_root = config.root

        for key, _ in config_root.sections("router  bgp"):
            self.assertEqual("router bgp", key)

        section_count = 0
        for _, _ in config_root.sections('router'):
            section_count += 1
        self.assertEqual(8, section_count)

    def test_table(self) -> None:
        config = parse_file(make_test_path("test3.conf"))
        config_root = config.root

        config_address = config_root.c_table("firewall address")
        dmz_address_1 = config_address.c_entry('DMZ')
        self.assertEqual(dmz_address_1.c_set('subnet').params, ['172.16.1.0', '255.255.255.0'])
        dmz_address_2 = config_address['DMZ']
        self.assertEqual(dmz_address_2['subnet'], FgtConfigSet(['172.16.1.0', '255.255.255.0']))

    def test_walk(self) -> None:
        config = parse_file(make_test_path("test3.conf"))
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
        config = parse_string(config_string)
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
        config = parse_string(config_string)
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
