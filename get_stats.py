from collections import namedtuple
import csv
from datetime import datetime
import os
import subprocess

Commit = namedtuple('Commit', ['hash', 'subject', 'date'])
WordCount = namedtuple('WordCount', ['filename', 'lines', 'words'])
FileWordCount = namedtuple('FileWordCount', ['date', 'subject', 'hash', 'lines', 'words'])

def get_log():
    commits = []
    for line in subprocess.check_output(['git', 'log', '--format=%h|%s|%ci']).split('\n'):
        if line:
            hash, subject, datestring = line.split('|')
            date = datetime.strptime(datestring[:16], '%Y-%m-%d %H:%M')
            commits.append(Commit(hash=hash, subject=subject, date=date))
    return commits


def checkout_commit(hash):
    subprocess.check_call(['git', 'checkout', hash])


def get_wordcounts():
    docs = [f for f in os.listdir('.') if f.endswith('.asciidoc')]
    wordcounts = []
    for filename in docs:
        with open(filename) as f:
            contents = f.read()
        lines = len(contents.split('\n'))
        words = len(contents.split())
        wordcounts.append(WordCount(filename, lines, words))
    return wordcounts


def main():
    commits = get_log()
    all_wordcounts = {}
    filenames = set()
    try:
        for commit in commits:
            checkout_commit(commit.hash)
            all_wordcounts[commit] = get_wordcounts()
            filenames.update(set(wc.filename for wc in all_wordcounts[commit]))

        with open('worcounts.csv', 'w') as csvfile:
            fieldnames = ['date', 'subject', 'hash']
            fieldnames.extend(sorted(filenames))
            writer = csv.DictWriter(csvfile, fieldnames)
            writer.writeheader()
            for commit, wordcounts in all_wordcounts.items():
                row = {}
                row['hash'] = commit.hash
                row['subject'] = commit.subject
                row['date'] = commit.date
                for wordcount in wordcounts:
                    row[wordcount.filename] = wordcount.lines
                writer.writerow(row)

    finally:
        checkout_commit('master')




if __name__ == '__main__':
    main()

