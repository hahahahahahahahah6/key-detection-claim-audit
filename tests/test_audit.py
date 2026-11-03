import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from key_detection_claim_audit import phrases
from key_detection_claim_audit.audit import audit, claims, evidence, main, GENERIC

EXPECTED_KEY = ('key detection', 'detects the musical key', 'detects musical key', 'detects the key of a song', 'detects the key of the audio', 'detects the key of music', 'detects song key', 'detects audio key', 'detect the musical key', 'detect musical key', 'musical key detection', 'song key detection', 'audio key detection', 'music key detection', 'identifies the musical key', 'identifies the key of a song', 'identifies song key', 'identify the musical key', 'estimates the musical key', 'estimates the key of a song', 'estimates song key', 'estimate the musical key', 'determines the musical key', 'determines the key of a song', 'determines song key', 'finds the musical key', 'finds the key of a song', 'finds song key', 'recognizes the musical key', 'recognises the musical key', 'key estimation', 'detects what key a song is in', 'detects what key the audio is in', 'tells you the key of a song', 'tells what key a song is in', 'reports the musical key', 'outputs the musical key', 'returns the musical key', 'key signature detection', 'detects the key signature', 'identifies the key signature', 'tonality detection', 'detects tonality', 'estimates tonality', 'detects whether a song is in a major or minor key', 'identifies the tonic', 'key analysis', 'musical key analysis', 'analyzes the musical key', 'analyses the musical key')
EXPECTED_NOKEY = ('no key detection', 'does not detect the musical key', 'without key detection', 'no musical key detection', 'does not detect musical key', 'does not identify the musical key', 'does not estimate the musical key', 'does not determine the musical key', 'no song key detection', 'does not detect song key', 'does not find the musical key', 'does not recognize the musical key', 'does not recognise the musical key', 'does not detect the key of a song', 'does not detect what key a song is in', 'does not tell you the key of a song', 'does not report the musical key', 'does not output the musical key', 'does not return the musical key', 'does not detect the key signature', 'does not identify the key signature', 'does not detect tonality', 'does not estimate tonality', 'key detection not supported')

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([str(self.root), '--json', *args])
        return code, json.loads(out.getvalue())

    def test_phrase_oracle(self):
        self.assertEqual(phrases.KEY, EXPECTED_KEY)
        self.assertEqual(phrases.NOKEY, EXPECTED_NOKEY)
        self.assertEqual((len(phrases.KEY), len(phrases.NOKEY)), (50, 24))

    def test_all_phrases(self):
        for phrase in EXPECTED_KEY:
            with self.subTest(phrase=phrase): self.assertEqual(claims(phrase), (True, False))
        for phrase in EXPECTED_NOKEY:
            with self.subTest(phrase=phrase): self.assertEqual(claims(phrase), (False, True))

    def test_good(self):
        self.put('README.md', 'Key detection')
        self.put('app.py', 'import essentia as e\ne.standard.KeyExtractor()')
        self.assertEqual(self.cli()[1]['verdict'], 'PASS')

    def test_bad(self):
        self.put('README.md', 'key detection')
        code, result = self.cli()
        self.assertEqual(code, 2)
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(result['findings'][0]['id'], 'documented-key-detection-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertTrue(result['findings'][0]['message'])

    def test_test_only(self):
        self.put('README.md', 'key detection')
        for name in ['tests/a.py', 'test_a.py', 'a_test.py']:
            with self.subTest(name=name):
                self.put(name, 'x.detect_key()')
                self.assertEqual(self.cli()[0], 0)
                self.assertEqual(self.cli()[1]['findings'][0]['severity'], 'MEDIUM')
                self.assertEqual(self.cli('--fail-on', 'MEDIUM')[0], 2)
                (self.root/name).unlink()

    def test_denial(self):
        self.put('README.md', 'no key detection')
        self.assertEqual(self.cli()[1]['verdict'], 'PASS')
        self.put('app.py', 'x.get_key()')
        code, result = self.cli()
        self.assertEqual(code, 2)
        self.assertEqual(result['findings'][0]['id'], 'documented-no-key-detection-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')

    def test_no_claim(self):
        self.assertEqual(self.cli()[1]['verdict'], 'PASS')

    def test_markdown(self):
        for marker in ['```', '~~~', '   ````']:
            self.assertEqual(claims(marker+'\nkey detection\n'+marker), (False, False))
        self.assertEqual(claims('`key detection`'), (True, False))
        self.assertEqual(claims("doesn't detect the musical key"), (False, True))
        self.assertEqual(claims('KEY-\nDETECTION'), (True, False))
        self.assertEqual(claims('monkey detection'), (False, False))
        self.assertEqual(claims('key\n\ndetection'), (False, False))

    def test_routes(self):
        expected = 'detect_key estimate_key get_key key_detect detect_musical_key estimate_musical_key get_musical_key musical_key_detect identify_key key_identify predict_key key_predict classify_key key_classify analyze_key analyse_key extract_key key_extract detect_tonality estimate_tonality get_tonality tonality_detect detect_key_signature estimate_key_signature detect_tonic estimate_tonic'.split()
        self.assertEqual(set(expected), GENERIC)
        for name in expected:
            for source in ['x.'+name+'()', 'from lib import '+name+'\n'+name+'()', 'from lib import '+name+' as alias\nalias()']:
                with self.subTest(source=source): self.assertTrue(evidence(source))
            self.assertFalse(evidence(name+'()'))
            self.assertFalse(evidence('def '+name+'(): pass\nx.'+name+'()'))
            self.assertFalse(evidence('from lib import '+name+' as alias\ndef alias(): pass\nalias()'))
        for source in ['import essentia\nessentia.KeyExtractor()', 'import essentia as e\ne.standard.KeyExtractor()', 'import essentia.standard\nessentia.standard.KeyExtractor()']:
            self.assertTrue(evidence(source))
        self.assertTrue(evidence('import essentia\ndef KeyExtractor(): pass\nessentia.KeyExtractor()'))

    def test_rejections(self):
        cases = ['import essentia', 'import keyfinder', 'librosa.load(x)', 'soundfile.read(x)', 'wave.open(x).readframes(1)', 'torchaudio.load(x)', 'sounddevice.rec()', 'mic.listen()', 'stream.read()', 'audio.play()', 'model.transcribe(x)', 'recognize_google(x)', 'engine.say(x)', 'vad.is_speech(x)', 'get_speech_timestamps(x)', 'Pipeline.from_pretrained("segmentation")', 'pvporcupine.create()', 'Model().predict(x)', 'x.detect_keyword()', 's.verify_files(a,b)', 'x.verify_speaker()', 'x.diarize()', 'x.reduce_noise()', 'x.enhance()', 'x.suppress_noise()', 'x.remove_noise()', 'acoustid.fingerprint_file(x)', 'Dejavu().recognize(x)', 'x.fingerprint_audio()', 'AudioTagging().inference(x)', 'YAMNet(x)', 'x.detect_sound_event()', 'pipeline("audio-classification")(x)', 'x.separate_stems()', 'demucs.separate(x)', 'Separator().separate(x)', 'librosa.beat.beat_track(x)', 'aubio.tempo()', 'essentia.RhythmExtractor()', 'x.detect_tempo()', 'librosa.yin(x)', 'librosa.piptrack(x)', 'crepe.predict(x)', 'aubio.pitch()', 'x.to_pitch()', 'x.detect_pitch()', 'librosa.onset.onset_detect(x)', 'x.onset_strength(x)', 'x.detect_onsets()', 'librosa.feature.chroma_cqt(x)', 'librosa.feature.chroma_cens(x)', 'librosa.feature.chroma_stft(x)', 'x.mfcc(x)', 'x.spectral_centroid(x)', 'essentia.Chromagram()', 'x.zero_crossing_rate(x)', 'essentia.ChordsDetection()', 'essentia.ChordsDetectionBeats()', 'x.detect_chords()', 'basic_pitch.predict(x)', 'MT3(x)', 'x.transcribe_notes(x)', 'music21.KeySignature(2)', 'music21.key.Key("C")', 'pychord.Key(x)', 'hashlib.md5(x)', 'hashlib.sha256(x)', 'x.filter(x)', 'x.equalize(x)', 'x.mix(x)', 'x.normalize(x)', 'x.detect_language(x)', 'x.translate(x)', 'x.KeyExtractor()', 'KeyExtractor()', 'subprocess.run(["keyfinder", x])', '"essentia KeyExtractor"', 'x.detect_key', 'from lib import detect_key\ndetect_key', 'bad syntax !']
        for source in cases:
            with self.subTest(source=source): self.assertFalse(evidence(source))

    def test_scope(self):
        self.put('README.md', 'key detection')
        self.put('one.py', 'import essentia as e')
        self.put('two.py', 'e.KeyExtractor()')
        self.assertEqual(self.cli()[0], 2)

    def test_paths(self):
        self.put('docs/sub/a.md', 'key detection')
        for name in ['fixtures/a.py', 'docs/a.py', 'examples/a.py']:
            self.put(name, 'x.detect_key()')
        self.assertEqual(self.cli()[0], 2)
        self.put('vendor/a.py', 'x.detect_key()')
        self.assertEqual(self.cli()[0], 0)
        self.assertEqual(self.cli('--ignore', 'vendor')[0], 2)
        self.assertEqual(self.cli('--ignore', 'vend')[0], 0)
        (self.root/'vendor/a.py').unlink()
        self.put('external.txt', 'x.detect_key()')
        (self.root/'linked.py').symlink_to(self.root/'external.txt')
        (self.root/'linked-dir').symlink_to(self.root/'fixtures', target_is_directory=True)
        self.assertEqual(self.cli()[0], 2)

    def test_errors(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(self.root/'missing')]), 1)
            with self.assertRaises(SystemExit) as error: main([])
            self.assertEqual(error.exception.code, 1)
            with self.assertRaises(SystemExit) as error: main(['--fail-on', 'bad'])
            self.assertEqual(error.exception.code, 1)

    def test_entry_points(self):
        result = subprocess.run([sys.executable, '-m', 'key_detection_claim_audit', '--version'], capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, '0.1.0'))
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as error: main(['--version'])
        self.assertEqual(error.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), '0.1.0')

    def test_self_audit(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(audit(root)['verdict'], 'PASS')

if __name__ == '__main__':
    unittest.main()
