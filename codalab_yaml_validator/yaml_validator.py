import argparse
import hashlib
import os
import yamale
import yaml

# Use versioning for detecting legacy style phase?

parser = argparse.ArgumentParser(description='Validate or compare bundles for use with Codalab competitions v2')
parser.add_argument(
    'dir_1',
    metavar='dir 1',
    nargs='?',
    type=str,
    help='Define the file path competition.yaml file'
)
parser.add_argument(
    'dir_2',
    metavar='dir 2',
    nargs='?',
    type=str,
    help='Define the file path competition.yaml file'
)

args = parser.parse_args()


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKING_DIR = os.path.abspath(args.dir_1)
SECOND_WORKING_DIR = os.path.abspath(args.dir_2) if args.dir_2 else None
YAML_FP = os.path.join(WORKING_DIR, 'competition.yaml')
SECOND_YAML_FP = os.path.join(SECOND_WORKING_DIR, 'competition.yaml') if SECOND_WORKING_DIR else None


def find_duplicate_indexes(obj_list):
    indexes = []
    duplicated = []
    for obj in obj_list:
        indexes.append(obj["index"]) if obj["index"] not in indexes else duplicated.append(obj["index"])
    return duplicated


def get_hash(working_dir, file_name):
    hasher = hashlib.md5()
    with open(os.path.join(working_dir, file_name), 'rb') as fp:
        hasher.update(fp.read())
        return hasher.hexdigest()


def get_hash_dict(working_dir, competition):
    task_files = [
        'scoring_program',
        'ingestion_program',
        'reference_data',
        'input_data',
    ]

    dir_hash_dict = {
        'image': get_hash(working_dir, competition['image'])
    }
    for page in competition['pages']:
        dir_hash_dict[page['title']] = get_hash(working_dir, page['file'])

    for task in competition['tasks']:
        for file in task_files:
            if file in task:
                dir_hash_dict[f'{task["name"]}_{file}'] = get_hash(working_dir, task[file])

    if 'solutions' in competition:
        for solution in competition['solutions']:
            dir_hash_dict[f'{solution["name"]}'] = get_hash(working_dir, solution['path'])

    return dir_hash_dict


def single_dir_validation():
    # ######### Initial Formatting Check ######### #
    schema = yamale.make_schema(os.path.join(BASE_DIR, 'schema.yaml'))
    data = yamale.make_data(YAML_FP)
    is_valid = yamale.validate(schema, data)
    if not is_valid:
        raise Exception("Empty input")
    print("Yaml file passed initial formatting tests")

    # ######### Deep Formatting Check ######### #

    with open(YAML_FP) as f:
        competition = yaml.load(f.read(), Loader=yaml.Loader)

    validation_errors = []

    # ###### Index Validation ###### #
    duplicated_indexes = {
        "task": find_duplicate_indexes(competition["tasks"]),
        "solution": find_duplicate_indexes(competition["solutions"]) if 'solutions' in competition else None,
        "phase": find_duplicate_indexes(competition["phases"]),
        "leaderboard": find_duplicate_indexes(competition["leaderboards"]),
    }

    for key, value in duplicated_indexes.items():
        validation_errors.append(f'Duplicate {key} index(s): {value}') if value else None

    for leaderboard in competition['leaderboards']:
        column_indexes = []
        for column in leaderboard['columns']:
            if column["index"] not in column_indexes:
                column_indexes.append(column["index"])
            else:
                validation_errors.append(f"Duplicate column index: {column['index']} on leaderboard: {leaderboard['title']}")

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
    if not os.path.exists(os.path.join(WORKING_DIR, competition['image'])):
        validation_errors.append(f'Image file - ({competition["image"]}) - not found')

    for page in competition['pages']:
        if not os.path.exists(os.path.join(WORKING_DIR, page['file'])):
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
                if not os.path.exists(os.path.join(WORKING_DIR, task[file])):
                    validation_errors.append(f'File for {file} - ({task[file]}) - not found')

    if 'solutions' in competition:
        for solution in competition['solutions']:
            if not os.path.exists(os.path.join(WORKING_DIR, solution['path'])):
                validation_errors.append(f'File for "{solution["name"]}" - ({solution["path"]}) - not found')

    # ###### Error Printing ###### #
    if validation_errors:
        print("Errors:")
        for error in validation_errors:
            print(f'- {error}')
    else:
        print("Valid Yaml!")


def compare_dirs():
    with open(YAML_FP) as f:
        competition1 = yaml.load(f.read(), Loader=yaml.Loader)

    with open(SECOND_YAML_FP) as f:
        competition2 = yaml.load(f.read(), Loader=yaml.Loader)

    errors = []

    dir1_hash_dict = get_hash_dict(WORKING_DIR, competition1)
    dir2_hash_dict = get_hash_dict(SECOND_WORKING_DIR, competition2)

    for key, hexdigest in dir1_hash_dict.items():
        if dir2_hash_dict[key] != hexdigest:
            errors.append(f'Files for {key} do not match')

    if errors:
        print("Errors:")
        for error in errors:
            print(f'- {error}')
    else:
        print("Directories match")


def main():
    if SECOND_WORKING_DIR:
        compare_dirs()
    else:
        single_dir_validation()


main()
