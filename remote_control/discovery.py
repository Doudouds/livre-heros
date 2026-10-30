"""Réponse aux recherches locales du lecteur, sans dépendance externe.

Le téléphone diffuse une demande UDP ; seuls les lecteurs répondent, en unicast.
Aucun code d'association ou jeton n'est annoncé sur le réseau.
"""
import ipaddress
import json
import re
import socket
import threading


DISCOVERY_PORT = 18766
SERVICE = 'portes-imaginaire-reader'
VERSION = 1
MAX_PACKET = 1024


def discovery_reply(data, *, http_port, name):
    if len(data) > MAX_PACKET:
        return None
    try:
        request = json.loads(data)
    except (ValueError, UnicodeError):
        return None
    if not isinstance(request, dict):
        return None
    nonce = request.get('nonce')
    if (request.get('service') != SERVICE or type(request.get('version')) is not int
            or request['version'] != VERSION or request.get('kind') != 'discover'
            or not isinstance(nonce, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', nonce)):
        return None
    return json.dumps({'service': SERVICE, 'version': VERSION, 'kind': 'reader',
                       'nonce': nonce, 'name': name[:100], 'port': http_port},
                      ensure_ascii=False, separators=(',', ':')).encode('utf-8')


class DiscoveryResponder:
    def __init__(self, http_port, *, host='0.0.0.0', port=DISCOVERY_PORT, name=None):
        self.http_port = http_port
        self.name = name or f'Les Portes de l’Imaginaire · {socket.gethostname()}'
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Un seul répondeur par machine ; ne pas partager silencieusement le port.
            self.socket.bind((host, port))
            self.socket.settimeout(0.2)
        except OSError:
            self.socket.close()
            raise
        self.port = self.socket.getsockname()[1]
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.run, name='reader-discovery', daemon=True)
        self.thread.start()

    def run(self):
        while not self.stopped.is_set():
            try:
                data, peer = self.socket.recvfrom(MAX_PACKET + 1)
                address = ipaddress.ip_address(peer[0])
                if address.is_global or address.is_unspecified or address.is_multicast:
                    continue
                reply = discovery_reply(data, http_port=self.http_port, name=self.name)
                if reply is not None:
                    self.socket.sendto(reply, peer)
            except socket.timeout:
                continue
            except OSError:
                # Une fermeture ou un paquet UDP refusé ne doit pas arrêter le lecteur.
                if self.stopped.is_set():
                    return
                self.stopped.wait(0.05)

    def close(self):
        self.stopped.set()
        self.socket.close()
        self.thread.join(timeout=1)
