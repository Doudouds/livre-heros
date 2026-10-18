"""Contrôler les WAV et mesurer des parcours avec les durées audio réelles."""
import argparse
import itertools
import json
from pathlib import Path

from audio.tts_batch import digest, read_manifest, read_wave, receipt_matches, receipt_path
from engine import Content, StoryEngine
from engine.content import ROOT


def audit(records, content=None):
    report = {'expected':len(records), 'valid':0, 'missing':0, 'invalid':0,
              'speech_verified':0, 'speech_unverified':0,
              'profiles':[], 'examples':[], 'game_timing':None, 'timing_target_met':None}
    durations, profiles = {}, set()
    for record in records:
        path = record['target']
        status = 'missing'
        if path.is_file():
            status = 'invalid'
            try:
                receipt = json.loads(receipt_path(path).read_text(encoding='utf-8'))
                profile = receipt['profile']
                identity = digest({'profile':profile,'text':record['text'],'segment_id':record['segment_id']})
                if receipt_matches(path, identity):
                    pcm = read_wave(path)
                    durations[record['segment_id']] = len(pcm.frames)/2/pcm.sample_rate
                    profiles.add(profile)
                    status = 'valid'
                    check = receipt.get('verification')
                    if isinstance(check,dict) and check.get('passed') is True and isinstance(check.get('policy'),str):
                        report['speech_verified'] += 1
                    else:
                        report['speech_unverified'] += 1
            except (OSError, ValueError, TypeError, KeyError):
                pass
        report[status] += 1
        if status != 'valid' and len(report['examples']) < 10:
            report['examples'].append({'file':str(path),'status':status})
    report['profiles'] = sorted(profiles)
    report['format_ready'] = report['valid'] == report['expected'] and len(profiles) == 1
    report['ready'] = report['format_ready'] and report['speech_verified'] == report['expected']
    if report['ready'] and content is not None:
        times = []
        complete_coverage = True
        for number, trio in enumerate(itertools.product(content.heroes,content.locations,content.items)):
            for arc in content.arcs:
                for policy in (0,1):
                    engine = StoryEngine(content,*trio,number,arc)
                    total = 0
                    while True:
                        key = engine.current['segment_id']
                        if key not in durations:
                            complete_coverage = False
                            break
                        total += durations[key]
                        if engine.finished:
                            break
                        if engine.current['kind'] == 'intro':
                            engine.advance()
                        else:
                            result = engine.choose(policy)
                            if result['segment_id'] not in durations:
                                complete_coverage = False
                                break
                            total += durations[result['segment_id']] + content.config['choice_seconds']
                            engine.advance()
                    if not complete_coverage:
                        break
                    times.append(total/60)
                if not complete_coverage:
                    break
            if not complete_coverage:
                break
        if complete_coverage:
            report['game_timing'] = dict(games=len(times),minimum_minutes=round(min(times),2),
                                       maximum_minutes=round(max(times),2),mean_minutes=round(sum(times)/len(times),2),
                                       choice_seconds_assumed=content.config['choice_seconds'],
                                       outside_18_22=sum(t<18 or t>22 for t in times))
            report['timing_target_met'] = report['game_timing']['outside_18_22'] == 0
        else:
            report['timing_note'] = 'Manifeste limité : les durées de toutes les parties ne peuvent pas être mesurées.'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'reports/tts_manifest.jsonl')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    report = audit(read_manifest(args.manifest,ROOT,args.output_dir),Content())
    text = json.dumps(report,ensure_ascii=False,indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text+'\n',encoding='utf-8')
    return 0 if report['ready'] and report['timing_target_met'] is not False else 1


if __name__ == '__main__':
    raise SystemExit(main())
