import os.path

DIRECTORIES_TO_EXCLUDE = ['.git', '.github', '.idea', '.obsidian', 'meta-notes', 'venv']

def make_moc_for_files(directory, files):
    output = ''
    for file in files:
        output += make_line_for_file(directory, file)
    return output


def make_line_for_file(directory, file):
    link_name, extension = os.path.splitext(file)
    if extension != '.md':
        link_name += extension
    return make_link_line(directory, link_name)


def make_link_line(directory, link_name):
    return f'-  [[{directory}/{link_name}|{link_name}]]\n'


def include_directory(d):
    return d not in DIRECTORIES_TO_EXCLUDE


def filter_directories(dirs):
    dirs[:] = [d for d in dirs if include_directory(d)]


def make_moc_for_sub_directories(directory, sub_directories):
    output = ''
    for sub_directory in sub_directories:
        output += make_line_for_sub_directory(directory, sub_directory)
    return output


def moc_name_for_sub_directory(sub_directory):
    name = sub_directory
    if name == '..':
        name = 'hub'
    return '🗂️ ' + name


def moc_file_path_for_directory(root):
    directory_name = os.path.basename(root)
    moc_file_basename = moc_name_for_sub_directory(directory_name)
    moc_file_path = os.path.join(root, moc_file_basename + ".md")
    return moc_file_path


def make_line_for_sub_directory(directory, sub_directory):
    path = directory + '/' + sub_directory
    file = moc_name_for_sub_directory(sub_directory)
    return make_link_line(path, file)

def index_content_for_directory(root, dirs, files):
    result = ''
    result += '%% Zoottelkeeper: Beginning of the autogenerated index file list  %%\n'
    result += make_moc_for_sub_directories(root, sorted(dirs))
    result += make_moc_for_files(root, sorted(files))
    result += '%% Zoottelkeeper: End of the autogenerated index file list  %%\n'
    return result
