import argparse
import datetime
import hashlib
import os
import re
import zipfile

import yamale
import yaml
from dateutil.parser import parse
from fuzzywuzzy import fuzz
from tempfile import TemporaryDirectory
from yamale.validators import DefaultValidators, Validator

parser = argparse.ArgumentParser(description='Validate or compare bundles for use with Codalab competitions v2')
parser.add_argument(
    'dir_1',
    metavar='dir 1',
    nargs=1,
    type=str,
    help='Define the file path to the bundle directory'
)
parser.add_argument(
    'dir_2',
    metavar='dir 2',
    nargs='?',
    type=str,
    help='Define the file path to the second bundle directory [optional]'
)

args = parser.parse_args()
dir_1 = args.dir_1[0]
dir_2 = args.dir_2 if args.dir_2 else None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

WORKING_DIR = os.path.abspath(dir_1)
FIRST_FILE_NAME = os.path.basename(WORKING_DIR)
if not os.path.isdir(WORKING_DIR):
    temp1 = TemporaryDirectory()
    with zipfile.ZipFile(WORKING_DIR) as zip_pointer:
        zip_pointer.extractall(temp1.name)
    WORKING_DIR = temp1.name

SECOND_WORKING_DIR = os.path.abspath(dir_2) if dir_2 else None
SECOND_FILE_NAME = os.path.basename(SECOND_WORKING_DIR) if SECOND_WORKING_DIR else None
if SECOND_WORKING_DIR and not os.path.isdir(SECOND_WORKING_DIR):
    temp2 = TemporaryDirectory()
    with zipfile.ZipFile(SECOND_WORKING_DIR) as zip_pointer:
        zip_pointer.extractall(temp2.name)
    SECOND_WORKING_DIR = temp2.name

YAML_FP = os.path.join(WORKING_DIR, 'competition.yaml')
SECOND_YAML_FP = os.path.join(SECOND_WORKING_DIR, 'competition.yaml') if SECOND_WORKING_DIR else None

# Regex to validate UUIDs: [0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}


class Date(Validator):
    """ Custom Date validator """
    tag = 'date'

    def _is_valid(self, value):
        if not isinstance(value, datetime.datetime):
            try:
                value = parse(value)
            except ValueError:
                pass
        return isinstance(value, datetime.datetime)


def find_duplicate_indexes(obj_list):
    indexes = []
    duplicated = []
    for obj in obj_list:
        indexes.append(obj["index"]) if obj["index"] not in indexes else duplicated.append(obj["index"])
    return duplicated


def get_hash(working_dir, file_name):
    hasher = hashlib.md5()
    path = os.path.join(working_dir, file_name)
    if os.path.isdir(path):
        return 'Not a zip file, hashes will not match. Manual validation of this folder is required.'
    with open(path, 'rb') as fp:
        hasher.update(fp.read())
        return hasher.hexdigest()


def get_file_hashes(obj, working_dir):
    files = [
        'scoring_program',
        'ingestion_program',
        'reference_data',
        'input_data',
        'path',
        'file',
    ]
    for file_name in files:
        if file_name in obj:
            obj[file_name] = get_hash(working_dir, obj[file_name])
    return obj


def assign_tasks(obj, tasks):
    task_dict = {task['old_index']: task for task in tasks}
    if 'tasks' in obj:
        obj['tasks'] = [task_dict[index] for index in obj['tasks']]
    return obj


def assign_solutions(obj, solutions):
    if 'solutions' in obj:
        obj['solutions'] = [solutions[index] for index in obj['solutions']]
    return obj


def set_index(index, obj):
    obj['old_index'] = obj['index']
    obj['index'] = index
    return obj


def parse_phase_dates(phase):
    start = phase.get('start')
    if start and not isinstance(start, datetime.datetime):
        phase['start'] = parse(start)
    end = phase.get('end')
    if end and not isinstance(end, datetime.datetime):
        phase['end'] = parse(end)
    return phase


def make_competition_dict(competition, working_dir):
    competition['image'] = get_hash(working_dir, competition['image'])
    if 'tasks' in competition:
        competition['tasks'] = sorted([get_file_hashes(task, working_dir) for task in competition['tasks']], key=lambda x: x['index'])
        competition['tasks'] = list(map(lambda enum_tasks: set_index(enum_tasks[0], enum_tasks[1]), enumerate(competition['tasks'])))
    if 'solutions' in competition:
        competition['solutions'] = {solution['index']: get_file_hashes(solution, working_dir) for solution in competition['solutions']}
    competition['phases'] = sorted([assign_solutions(assign_tasks(phase, competition['tasks']), competition['solutions']) for phase in competition['phases']], key=lambda x: x['index'])
    competition['phases'] = list(map(lambda enum_phases: set_index(enum_phases[0], parse_phase_dates(enum_phases[1])), enumerate(competition['phases'])))
    if 'pages' in competition:
        competition['pages'] = [get_file_hashes(page, working_dir) for page in competition['pages']]
    return competition


def dict_similarity(obj1, obj2):
    similarity = 0
    keys1 = obj1.keys()
    keys2 = obj2.keys()
    for key in keys1:
        if key in obj2:
            if obj1[key] == obj2[key]:
                similarity += 1
            elif key in ['title', 'name', 'description']:
                similarity += fuzz.ratio(obj1[key], obj2[key]) / 100
    k1_length = len(keys1)
    k2_length = len(keys2)
    if 'key' in obj1 and 'key' not in obj2:
        k1_length -= 1
    if 'key' in obj2 and 'key' not in obj1:
        k2_length -= 1
    return similarity / ((k1_length + k2_length) / 2)


def compare(d1, d2, label):
    defaults = {
        'is_public': False,
        'max_submissions': None,
        'max_submissions_per_day': None,
        'execution_time_limit_ms': 600,
        'sorting': 'desc',
        'computation': None,
        'computation_indexes': None,
    }
    differences = []
    if 'old_index' not in d1:
        d1['old_index'] = d1['index']
    if 'old_index' not in d2:
        d2['old_index'] = d2['index']
    for key in d1.keys():
        if key in ['index', 'old_index']:
            continue
        if key not in d2:
            if key == 'key':
                continue
            if key in defaults:
                if d1[key] != defaults[key]:
                    differences.append(f'- Default Value Change\n'
                                       f'  - [{FIRST_FILE_NAME}] {label} index:{d1["old_index"]} ({key}) = {d1[key]}\n'
                                       f'  - [{SECOND_FILE_NAME}] {label} index:{d2["old_index"]} ({key}) = None (defaults to: {defaults[key]})')
            else:
                differences.append(f'- Missing value\n'
                                   f'  - [{FIRST_FILE_NAME}] {label} index:{d1["old_index"]} ({key}) = {d1[key]}'
                                   f'  - [{SECOND_FILE_NAME}] {label} index:{d2["old_index"]} ({key}) = None')
            continue
        if key == 'tasks' and label == 'Solution':
            continue
        if key == 'tasks':
            task_array = get_similarity_array(d1[key], d2[key])
            for t1, t2 in task_array:
                differences += compare(d1['tasks'][t1], d2['tasks'][t2], 'Task')
            d1_tasks = [task[0] for task in task_array]
            d2_tasks = [task[1] for task in task_array]
            for task in d1['tasks']:
                if task['index'] not in d1_tasks:
                    differences.append(f'- No Equivalent Value\n'
                                       f'  - [{FIRST_FILE_NAME}] Task index:{task["old_index"]} has no equivalent {label} in [{SECOND_FILE_NAME}]')
            for task in d2['tasks']:
                if task['index'] not in d2_tasks:
                    differences.append(f'- No Equivalent Value\n'
                                       f'  - [{SECOND_FILE_NAME}] Task index:{task["old_index"]} has no equivalent {label} in [{FIRST_FILE_NAME}]')
        elif key == 'solutions':
            solution_array = get_similarity_array(d1[key], d2[key])
            for s1, s2 in solution_array:
                differences += compare(d1['solutions'][s1], d2['solutions'][s2], 'Solution')
        elif key == 'columns':
            column_array = get_similarity_array(d1[key], d2[key])
            for c1, c2 in column_array:
                differences += compare(d1['columns'][c1], d2['columns'][c2], 'Column')
        elif d1[key] != d2[key]:
            differences.append(f'- Mismatched values\n'
                               f'  - [{FIRST_FILE_NAME}] {label} index:{d1["old_index"]} ({key}) = {d1[key]}\n'
                               f'  - [{SECOND_FILE_NAME}] {label} index:{d2["old_index"]} ({key}) = {d2[key]}')
    for key in d2.keys():
        if key in ['index', 'old_index']:
            continue
        if key not in d1:
            if key == 'key':
                continue
            if key in defaults:
                if d2[key] != defaults[key]:
                    differences.append(f'- Default Value Change\n'
                                       f'  - [{FIRST_FILE_NAME}] {label} index:{d1["old_index"]} ({key}) = None (defaults to: {defaults[key]})\n'
                                       f'  - [{SECOND_FILE_NAME}] {label} index:{d2["old_index"]} ({key}) = {d2[key]}')
            else:
                differences.append(f'- Missing value\n'
                                   f'  - [{FIRST_FILE_NAME}] {label} index:{d1["old_index"]} ({key}) = None'
                                   f'  - [{SECOND_FILE_NAME}] {label} index:{d2["old_index"]} ({key}) = {d2[key]}')
            continue
    return differences


def get_similarity_array(list1, list2):
    similarity_array = []
    for obj1 in list1:
        values = []
        for obj2 in list2:
            values.append(dict_similarity(obj1, obj2))
        similarity_array.append(values)
    position_array = []
    while sum(map(sum, similarity_array)) > 0:
        max_similarity = 0
        position = []
        for index1, row in enumerate(similarity_array):
            for index2, value in enumerate(row):
                if value > max_similarity:
                    max_similarity = value
                    position = [index1, index2]
        position_array.append(position)
        row = position[0]
        col = position[1]
        similarity_array[row] = [0 for _ in similarity_array[row]]
        for row_index in range(len(similarity_array)):
            similarity_array[row_index][col] = 0
    return position_array


def single_dir_validation(yaml_fp, working_dir, silent=False):
    # ######### Initial Formatting Check ######### #
    validators = DefaultValidators.copy()  # This is a dictionary
    validators[Date.tag] = Date
    schema = yamale.make_schema(os.path.join(BASE_DIR, 'schema.yaml'), validators=validators)
    data = yamale.make_data(yaml_fp)
    is_valid = yamale.validate(schema, data)
    if not is_valid:
        raise Exception("Empty input")
    if not silent:
        print("Yaml file passed initial formatting tests")

    # ######### Deep Formatting Check ######### #
    re_uuid = re.compile(r'^[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}$')
    with open(yaml_fp) as f:
        competition = yaml.load(f.read(), Loader=yaml.Loader)

    validation_errors = []
    warnings = []

    # ###### Index Validation ###### #
    duplicated_indexes = {
        "task": find_duplicate_indexes(competition["tasks"]),
        "solution": find_duplicate_indexes(competition["solutions"]) if 'solutions' in competition else None,
        "phase": find_duplicate_indexes(competition["phases"]),
        "leaderboard": find_duplicate_indexes(competition["leaderboards"]),
    }

    for key, value in duplicated_indexes.items():
        validation_errors.append(f'Duplicate {key} index(es): {value}') if value else None

    for leaderboard in competition['leaderboards']:
        column_indexes = []
        for column in leaderboard['columns']:
            if column["index"] not in column_indexes:
                column_indexes.append(column["index"])
            else:
                validation_errors.append(f"Duplicate column index: {column['index']} on leaderboard: {leaderboard['title']}")

    # Tasks Validation
    for task in competition['tasks']:
        task_keys = task.keys()
        if 'key' in task_keys:
            if any([key not in ['key', 'index'] for key in task_keys]):
                warnings.append(f'Task with index {task["index"]}: If specifying a key, all other fields will be ignored on upload')
        else:
            for required_field in ['name', 'description', 'scoring_program']:
                if required_field not in task_keys:
                    validation_errors.append(f'Task with index {task["index"]}: missing required field - {required_field}')

    # Solution Tasks
    if 'solutions' in competition:
        for solution in competition['solutions']:
            for index in set([task for task in solution['tasks']]).difference(set(map(lambda t: t['index'], competition['tasks']))):
                validation_errors.append(f'Task index: "{index}" on solution: "{solution["name"]}" not present in tasks')

    # Phase Tasks
    for phase in competition['phases']:
        for index in set([task for task in phase['tasks']]).difference(set(map(lambda t: t['index'], competition['tasks']))):
            validation_errors.append(f'Task index: "{index}" on phase: "{phase["name"]}" not present in tasks')

    # Phase Solutions
    for phase in competition['phases']:
        if 'solutions' in phase:
            for index in set([solution for solution in phase['solutions']]).difference(set(map(lambda s: s['index'], competition['solutions']))):
                validation_errors.append(f'Solution index: "{index}" on phase: "{phase["name"]}" not present in solutions')

    # ###### Leaderboard Key Validation ###### #
    leaderboard_keys = []
    duplicate_leaderboard_keys = []
    column_errors = []
    for leaderboard in competition['leaderboards']:
        if leaderboard['key'] in leaderboard_keys:
            duplicate_leaderboard_keys.append(leaderboard['key'])
        else:
            leaderboard_keys.append(leaderboard['key'])

        column_keys = []
        for column in leaderboard['columns']:
            if column["key"] not in column_keys:
                column_keys.append(column["key"])
            else:
                column_errors.append(f"Duplicate column key: {column['key']} on leaderboard: {leaderboard['title']}")

    if duplicate_leaderboard_keys:
        validation_errors.append(f'Duplicate leaderboard keys: {duplicate_leaderboard_keys}')
    validation_errors += column_errors

    # ###### File Path Validation ###### #
    if not os.path.exists(os.path.join(working_dir, competition['image'])):
        validation_errors.append(f'Image file - ({competition["image"]}) - not found')

    for page in competition['pages']:
        if not os.path.exists(os.path.join(working_dir, page['file'])):
            validation_errors.append(f'File for page "{page["title"]}" - ({page["file"]}) - not found')

    task_files = [
        'scoring_program',
        'ingestion_program',
        'reference_data',
        'input_data',
    ]

    for task in competition['tasks']:
        for file in task_files:
            if file in task:
                if not os.path.exists(os.path.join(working_dir, task[file])):
                    # File doesn't exist, see if it was a UUID
                    if re.match(re_uuid, task[file]) is None:
                        validation_errors.append(f'File for {file} - ({task[file]}) - not found')

    if 'solutions' in competition:
        for solution in competition['solutions']:
            if not os.path.exists(os.path.join(working_dir, solution['path'])):
                validation_errors.append(f'File for "{solution["name"]}" - ({solution["path"]}) - not found')

    # ###### Warning Printing ###### #
    if warnings and not silent:
        print('WARNINGS:')
        for warning in warnings:
            print(f'- {warning}')
    # ###### Error Printing ###### #
    if validation_errors:
        print("ERRORS:")
        for error in validation_errors:
            print(f'- {error}')
        return False
    else:
        if not silent:
            print("Yaml bundle is valid")
        return competition


def compare_dirs():
    competition1 = single_dir_validation(YAML_FP, WORKING_DIR, silent=True)
    competition2 = single_dir_validation(SECOND_YAML_FP, SECOND_WORKING_DIR, silent=True)

    if not competition1 or not competition2:
        return

    competition1 = make_competition_dict(competition1, WORKING_DIR)
    competition2 = make_competition_dict(competition2, SECOND_WORKING_DIR)

    differences = []

    if competition1['title'] != competition2['title']:
        differences.append(f'- Mismatched values\n'
                           f'  - [{FIRST_FILE_NAME}] Title = {competition1["title"]}\n'
                           f'  - [{SECOND_FILE_NAME}] Title = {competition2["title"]}')

    if competition1['image'] != competition2['image']:
        differences.append('- Image files do not match')

    phase_array = get_similarity_array(competition1['phases'], competition2['phases'])

    for ph1, ph2 in phase_array:
        phase1 = competition1['phases'][ph1]
        phase2 = competition2['phases'][ph2]
        differences += compare(phase1, phase2, 'Phase')

    for phase in competition1['phases']:
        if phase['index'] not in [p[0] for p in phase_array]:
            differences.append(f'- No Equivalent Value\n'
                               f'  - [{FIRST_FILE_NAME}] Phase index:{phase["index"]} has no equivalent Phase in [{SECOND_FILE_NAME}]')
    for phase in competition2['phases']:
        if phase['index'] not in [p[1] for p in phase_array]:
            differences.append(f'- No Equivalent Value\n'
                               f'  - [{SECOND_FILE_NAME}] Phase index:{phase["index"]} has no equivalent Phase in [{FIRST_FILE_NAME}]')

    leaderboard_array = get_similarity_array(competition1['leaderboards'], competition2['leaderboards'])
    for l1, l2 in leaderboard_array:
        differences += compare(competition1['leaderboards'][l1], competition2['leaderboards'][l2], 'Leaderboard')

    if differences:
        print('\nDifferences:\n')
        for diff in differences:
            print(diff + '\n')
    else:
        print('\nNo significant differences between these files\n')


def main():
    if SECOND_WORKING_DIR:
        compare_dirs()
    else:
        single_dir_validation(YAML_FP, WORKING_DIR)
