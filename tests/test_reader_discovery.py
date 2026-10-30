import json
import socket
import unittest
from unittest.mock import MagicMock, patch

from main_remote import main
from remote_control.discovery import DiscoveryResponder, SERVICE, discovery_reply


def request(nonce='current-search', **values):
    return json.dumps({'service': SERVICE, 'version': 1, 'kind': 'discover', 'nonce': nonce, **values}).encode()


class DiscoveryTests(unittest.TestCase):
    def test_reply_identifies_reader_and_actual_port_without_credentials(self):
        reply = json.loads(discovery_reply(request(), http_port=8766, name='Mon Raspberry Pi'))
        self.assertEqual(reply, {'service': SERVICE, 'version': 1, 'kind': 'reader',
                                 'nonce': 'current-search', 'port': 8766, 'name': 'Mon Raspberry Pi'})
        self.assertNotIn('token', reply)
        self.assertNotIn('code', reply)

    def test_unrelated_malformed_or_oversized_packets_are_ignored(self):
        for data in (b'hello', b'[]', b'\xff', b'x' * 1025, request(service='other'),
                     request(version=True), request(version=2), request(kind='reader'),
                     request(nonce=''), request(nonce='x' * 65), request(nonce='bad\nvalue')):
            self.assertIsNone(discovery_reply(data, http_port=8765, name='PC'))

    def test_real_udp_roundtrip_and_listener_survives_bad_packet(self):
        responder = DiscoveryResponder(9876, host='127.0.0.1', port=0, name='PC de test')
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(0.1)
                client.sendto(b'not-json', ('127.0.0.1', responder.port))
                with self.assertRaises(socket.timeout):
                    client.recvfrom(2048)
                client.settimeout(1)
                client.sendto(request(), ('127.0.0.1', responder.port))
                data, peer = client.recvfrom(2048)
                self.assertEqual(peer[0], '127.0.0.1')
                self.assertEqual(json.loads(data)['port'], 9876)
                self.assertEqual(json.loads(data)['nonce'], 'current-search')
        finally:
            responder.close()
        self.assertFalse(responder.thread.is_alive())
        responder.close()

    def test_broadcast_request_receives_unicast_reply(self):
        responder = DiscoveryResponder(8765, port=0)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.bind(('127.0.0.1', 0))
                client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                client.settimeout(1)
                client.sendto(request(), ('127.255.255.255', responder.port))
                data, _ = client.recvfrom(2048)
                self.assertEqual(json.loads(data)['service'], SERVICE)
        finally:
            responder.close()

    def test_launcher_closes_discovery_on_interrupt_and_can_disable_it(self):
        server = MagicMock(server_port=9876)
        server.serve_forever.side_effect = KeyboardInterrupt
        with patch('main_remote.Content'), patch('main_remote.PlaybackService'), \
                patch('main_remote.RemoteServer', return_value=server), \
                patch('main_remote.local_addresses', return_value=['127.0.0.1']), \
                patch('main_remote.DiscoveryResponder') as discovery, patch('builtins.print'):
            self.assertEqual(main([]), 0)
            discovery.assert_called_once_with(9876)
            discovery.return_value.close.assert_called_once()
            discovery.reset_mock()
            self.assertEqual(main(['--no-discovery']), 0)
            discovery.assert_not_called()
            self.assertEqual(main(['--host', '127.0.0.1']), 0)
            discovery.assert_not_called()

    def test_discovery_failure_keeps_manual_connection_available(self):
        server = MagicMock(server_port=9876)
        server.serve_forever.side_effect = KeyboardInterrupt
        with patch('main_remote.Content'), patch('main_remote.PlaybackService'), \
                patch('main_remote.RemoteServer', return_value=server), \
                patch('main_remote.local_addresses', return_value=[]), \
                patch('main_remote.DiscoveryResponder', side_effect=OSError('Port occupied')), \
                patch('builtins.print'):
            self.assertEqual(main([]), 0)
            server.serve_forever.assert_called_once()


if __name__ == '__main__':
    unittest.main()
