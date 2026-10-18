import sys
import time
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root),str(root/'tmp/emotions_asr_deps')]
from faster_whisper import WhisperModel
from audio.tts_batch import atomic_json
from audio.speech_verification import compare_transcript, IncompleteSpeech
from engine.content import Content
plan = Content.read(root/'reports/roi_grenouille/audio_premier_segment.json')
model_dir = root/'audio/experiments/emotions/asr_cache/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120'
started = time.monotonic()
model = WhisperModel(str(model_dir),device='cpu',compute_type='int8',local_files_only=True)
segments,info = model.transcribe(plan['rejected_file'],language='fr',beam_size=5,
                                temperature=0,condition_on_previous_text=False,vad_filter=True)
timed = [dict(start=s.start,end=s.end,text=s.text.strip()) for s in segments]
transcript = ' '.join(s['text'] for s in timed)
try:
    result = compare_transcript(plan['text'],transcript)
except IncompleteSpeech as exc:
    result = exc.report
result.update(segments=timed,method='faster-whisper-small-vad',seconds=time.monotonic()-started)
atomic_json(root/'reports/roi_grenouille/controle_integral_vad.json',result)
print(result)
