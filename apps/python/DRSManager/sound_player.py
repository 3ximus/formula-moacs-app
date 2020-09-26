from threading import Thread, Event
try:
    from stdlib import winsound
except ImportError:
    import winsound

class SoundPlayer(object):
    def __init__(self, filename):
        self.filename = filename
        self._play_event = Event()
        self.thread = Thread(target=self._worker)
        self.thread.daemon = True
        self.thread.start()
        self._audio_cache = {}
    
    def play(self, filename=None):
        if filename is not None:
            self.filename = filename
        self._play_event.set()
    
    def stop(self):
        self._play_event.clear()

    def _worker(self):
        while True:
            self._play_event.wait()
            winsound.PlaySound(self.filename, winsound.SND_FILENAME)

if __name__ == "__main__":
    import time
    pl = SoundPlayer("beep.wav")
    pl.play()
    time.sleep(1)
    

