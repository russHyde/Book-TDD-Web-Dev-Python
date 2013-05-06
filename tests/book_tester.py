# -*- coding: utf-8 -*-
import os
import re
import signal
import subprocess
import shutil
import tempfile
import unittest
from lxml import html

base_dir = os.path.split(os.path.dirname(__file__))[0]
raw_html = open(os.path.join(base_dir, 'book.html')).read()
parsed_html = html.fromstring(raw_html)


class CodeListing(object):
    def __init__(self, filename, contents):
        self.filename = filename
        self.contents = contents
        self.was_written = False



class Command(unicode):
    def __init__(self, a_string):
        self.was_run = False
        unicode.__init__(a_string)



class Output(unicode):
    def __init__(self, a_string):
        self.was_checked = False
        unicode.__init__(a_string)



def parse_listing(listing):
    if listing.getnext().get('class') == 'paragraph caption':
        filename = listing.getnext().text_content()
        contents = listing.text_content().strip().replace('\r\n', '\n')
        return [CodeListing(filename, contents)]

    else:
        commands = get_commands(listing)
        lines = listing.text_content().strip().replace('\r\n', '\n').split('\n')
        outputs = []
        output_after_command = ''
        for line in lines:
            commands_in_this_line = filter(line.endswith, commands)
            if commands_in_this_line:
                if output_after_command:
                    outputs.append(Output(output_after_command.rstrip()))
                    output_after_command = ''
                outputs.append(Command(commands_in_this_line[0]))
            else:
                output_after_command += line + '\n'
        if output_after_command:
            outputs.append(Output(output_after_command.rstrip()))
        return outputs


def get_commands(node):
    commands = [
        el.text_content()
        for el in node.cssselect('pre code strong')
    ]
    if commands.count("git rm --cached superlists/"):
        ## hack -- listings with a star in are weird
        fix_pos = commands.index("git rm --cached superlists/")
        commands.remove("git rm --cached superlists/")
        commands.remove(".pyc")
        commands.insert(fix_pos, "git rm --cached superlists/*.pyc")

    return commands


def write_to_file(codelisting, cwd):
    if "[..." not in codelisting.contents:
        new_contents = codelisting.contents
    else:
        with open(os.path.join(cwd, codelisting.filename)) as f:
            old_contents = f.read()
        new_contents = ''

        lines = codelisting.contents.split('\n')
        old_lines = old_contents.strip().split('\n')
        if codelisting.contents.count("[...") == 1:
            split_line = [l for l in lines if "[..." in l][0]
            indent = split_line.split("[...")[0]
            split_line_pos = lines.index(split_line)
            lines_before = lines[:split_line_pos]
            last_line_before = lines_before[-1]
            lines_after = lines[split_line_pos + 1:]

            last_old_line = [
                l for l in old_lines if l.strip() == last_line_before.strip()
            ][0]
            last_old_line_pos = old_lines.index(last_old_line)
            old_lines_after = old_lines[last_old_line_pos + 1:]

            # special-case: stray browser.quit in chap. 2
            if 'rest of comments' in split_line:
                assert old_lines_after[-1] == 'browser.quit()'
                old_lines_after.pop()

            newline_indent = '\n' + indent

            new_contents += '\n'.join(lines_before)
            new_contents += newline_indent
            new_contents += newline_indent.join(old_lines_after)
            new_contents += '\n'
            new_contents += '\n'.join(lines_after)

        elif codelisting.contents.startswith("[...]") and codelisting.contents.endswith("[...]"):
            first_line_to_find = lines[1]
            last_old_line = [
                l for l in old_lines if l.strip() == first_line_to_find.strip()
            ][0]
            last_old_line_pos = old_lines.index(last_old_line)
            indent = (len(last_old_line) - len(last_old_line.lstrip())) * " "

            second_line_to_find = lines[-2]
            old_resume_line = [
                l for l in old_lines if l.strip() == second_line_to_find.strip()
            ][0]
            old_lines_resume_pos = old_lines.index(old_resume_line)

            newline_indent = '\n' + indent
            new_contents += '\n'.join(old_lines[:last_old_line_pos + 1])
            new_contents += newline_indent
            new_contents += newline_indent.join(lines[2:-2])
            new_contents += '\n'.join(old_lines[old_lines_resume_pos - 1:])


    new_contents = '\n'.join(
        l.rstrip(' #') for l in new_contents.split('\n')
    )

    if not new_contents.endswith('\n'):
        new_contents += '\n'

    with open(os.path.join(cwd, codelisting.filename), 'w') as f:
        f.write(new_contents)

    codelisting.was_written = True


class ChapterTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.processes = []


    def tearDown(self):
        for process in self.processes:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except OSError:
                print 'error killing', process._command
        shutil.rmtree(self.tempdir)


    def start_with_checkout(self, chapter):
        local_repo_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            '../source/chapter_%d/superlists' % (chapter,)
        ))
        self.run_command(Command('mkdir superlists'), cwd=self.tempdir)
        self.run_command(Command('git init .'))
        self.run_command(Command('git remote add repo %s' % (local_repo_path,)))
        self.run_command(Command('git fetch repo'))
        self.run_command(Command('git checkout chapter_%s' % (chapter - 1,)))


    def write_to_file(self, codelisting):
        print 'writing to file', codelisting.filename
        write_to_file(codelisting, os.path.join(self.tempdir, 'superlists'))
        print 'wrote', open(os.path.join(self.tempdir, 'superlists', codelisting.filename)).read()


    def run_command(self, command, cwd=None):
        self.assertEqual(type(command), Command)
        if cwd is None:
            cwd = os.path.join(self.tempdir, 'superlists')
        print 'running command', command
        process = subprocess.Popen(
            command, shell=True, cwd=cwd, executable='/bin/bash',
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            preexec_fn=os.setsid
        )
        command.was_run = True
        process._command = command
        self.processes.append(process)
        print 'directory listing is now', os.listdir(self.tempdir)
        if 'runserver' in command:
            return #test this another day
        process.wait()
        return process.stdout.read().decode('utf8')


    def assert_console_output_correct(self, actual, expected, ls=False):
        self.assertEqual(type(expected), Output)

        # special case for git init
        if self.tempdir in actual:
            actual = actual.replace(self.tempdir, '/workspace')

        if ls:
            actual=actual.strip()
            self.assertItemsEqual(actual.split('\n'), expected.split())

        else:
            actual_text = actual.strip().replace('\t', '       ')
            expected_text = expected.replace(' -----', '------')
            actual_text = re.sub(
                r"Ran (\d+) tests? in \d+\.\d\d\ds",
                r"Ran \1 tests in X.Xs",
                actual_text,
            )
            expected_text = re.sub(
                r"Ran (\d+) tests? in \d+\.\d\d\ds",
                r"Ran \1 tests in X.Xs",
                expected_text,
            )
            actual_text = re.sub(
                r"index .......\.\........ 100644",
                r"index XXXXXXX\.\.XXXXXXX 100644",
                actual_text,
            )
            expected_text = re.sub(
                r"index .......\.\........ 100644",
                r"index XXXXXXX\.\.XXXXXXX 100644",
                expected_text,
            )
            if expected_text.endswith("[...]"):
                expected_lines = expected_text.split('\n')[:-1]
                expected_text = '\n'.join(l.strip() for l in expected_lines)
                actual_lines = actual_text.split('\n')[:len(expected_lines)]
                actual_text = '\n'.join(l.strip() for l in actual_lines)
            self.assertMultiLineEqual(actual_text, expected_text)
        expected.was_checked = True


    def assert_directory_tree_correct(self, expected_tree, cwd=None):
        actual_tree = self.run_command(Command('tree -I *.pyc --noreport'), cwd)
        # special case for first listing:
        if expected_tree.startswith('superlists/'):
            print 'FIXING'
            expected_tree = Output(
                expected_tree.replace('superlists/', '.', 1)
            )
        self.assert_console_output_correct(actual_tree, expected_tree)
        return expected_tree

