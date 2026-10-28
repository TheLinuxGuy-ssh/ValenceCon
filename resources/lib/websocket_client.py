from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import json
import threading
import time

import xbmc
import xbmcaddon
import xbmcgui

from .valence import api
from .functions import play_action
from .lazylogger import LazyLogger
from .jsonrpc import JsonRpc
from .kodi_utils import HomeWindow
from .utils import load_user_details

log = LazyLogger(__name__)


class WebSocketClient(threading.Thread):
    """
    Valence doesn't have WebSocket support like Jellyfin.
    This class is kept for compatibility but will not connect.
    """

    _shared_state = {}

    _client = None
    _stop_websocket = False
    _library_monitor = None

    def __init__(self, library_change_monitor):

        self.__dict__ = self._shared_state
        self.monitor = xbmc.Monitor()

        self._library_monitor = library_change_monitor
        self.websocket_error = False
        
        log.debug("Valence doesn't support WebSocket - WebSocketClient disabled")

        threading.Thread.__init__(self)

    def on_message(self, ws, message):
        """Not used for Valence"""
        pass

    def _library_changed(self, data):
        log.debug("Library_Changed: {0}".format(data))
        self._library_monitor.check_for_updates()

    def _play(self, data):
        """Not used for Valence"""
        pass

    def _playstate(self, data):
        """Not used for Valence"""
        pass

    def _general_commands(self, data):
        """Not used for Valence"""
        pass

    def on_open(self, ws):
        """Not used for Valence"""
        pass

    def on_error(self, ws, error):
        """Not used for Valence"""
        pass

    def run(self):
        """
        Valence doesn't have WebSocket support.
        This thread will just sleep and exit when monitor aborts.
        """
        log.debug("WebSocketClient disabled for Valence (no WebSocket endpoint)")
        
        while not self.monitor.abortRequested():
            if self.monitor.waitForAbort(60):
                return
        
        log.debug("WebSocketClient Stopped")

    def stop_client(self):
        self._stop_websocket = True
        if self._client is not None:
            self._client.close()
        log.debug("Stopping WebSocket (stop_client called)")

    def send_keepalive(self, ws):
        """Not used for Valence"""
        pass

    def schedule_keepalive(self, ws):
        """Not used for Valence"""
        pass