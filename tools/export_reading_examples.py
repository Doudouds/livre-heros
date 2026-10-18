"""Six parcours lisibles pour relire le contenu et un journal V2 de démonstration."""
from pathlib import Path

from engine import Content, StoryEngine
from engine.content import ROOT
from tools.export_tts_manifest import export


def main():
    content = Content()
    lines = ['# Six contes réécrits — exemples de parcours', '',
             'Ces lectures montrent un parcours par conte. Le jeu offre d’autres choix, résultats et conclusions.',
             'Les questions ci-dessous sont incluses à la fin de chaque WAV de scène.', '']
    configurations = [('knight','castle','sword'),('keeper','mountain','amulet'),
                      ('mage','forest','book'),('rogue','city','key'),
                      ('explorer','forest','compass'),('knight','ruins','sword')]
    for number, arc in enumerate(('lantern','bell','names','feather','atlas','rain')):
        hero,location,item = configurations[number]
        engine = StoryEngine(content,hero,location,item,42+number,arc)
        lines += ['## '+engine.arc['title'], '', engine.arc['description'], '',
                  f"Configuration : {content.heroes[hero]['label']} ; {content.locations[location]['label']} ; {content.items[item]['label']}.", '']
        while True:
            lines += ['### '+engine.current['title'], '', engine.current['spoken_text'], '']
            if engine.finished:
                break
            if engine.current['kind'] == 'intro':
                engine.advance()
            else:
                result = engine.choose(engine.state.story_progress % 2)
                lines += [f"**Dans cet exemple : choix {result['choice_index']+1}.**", '', result['text'], '']
                engine.advance()
        if number == 0:
            journal = ROOT/'reports/exemple_session.json'
            engine.export_session(journal)
            export(content,ROOT/'reports/tts_exemple_session.jsonl',journal)
    destination = ROOT/'docs/lecture_des_six_contes.md'
    destination.write_text('\n'.join(lines),encoding='utf-8')
    print(f'Six lectures exportées dans {destination}. Journal exemple et manifeste de 26 segments renouvelés.')


if __name__ == '__main__':
    main()
