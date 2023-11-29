import os
import argparse
import json
import shutil
import tarfile
import tempfile
import requests
import getpass
from git import Repo

UPLOAD_ENDPOINT = "https://api.deltafunctions.io/upload_project"
AUTH_API_ENDPOINT = "https://api.deltafunctions.io/upload_project"
CLIENT_API_KEY = "123456789"

user_id = ''
user_jwt_token = ''

system_temp_dir = os.path.join(tempfile.gettempdir(), '.deltafx')

def create_dockerfile(repo_path, image_name):
    dockerfile_content = f"""
# Use an official Python runtime as a parent image
FROM python:3.8

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV NAME World

# Run app.py when the container launches
CMD ["python", "app.py"]
"""
    
    with open(os.path.join(repo_path, 'Dockerfile'), 'w') as dockerfile:
        dockerfile.write(dockerfile_content)


def create_packagejson(project_name, version, description, main_script):
    pass

def create_project(project_path):
    os.makedirs(project_path, exist_ok=True)
    print(f"Project folder '{project_path}' created")

def init_empty_git_repo(project_path):
    repo = Repo.init(project_path)
    print(f"Initialized an empty git repo in '{project_path}'")
    return repo

def init_project(project_path):
    # create the project folder
    create_project(project_path)
    # init git repo
    init_empty_git_repo(project_path)

def generate_dockerfile(repo_path, image_name):
    create_dockerfile(repo_path, image_name)

def build_project(repo_path, project_name, branch=None, commit=None):
    """ Build project at the given branch and commit """
    build_dir = os.path.join(repo_path, '.delfx', 'build')

    if commit is not None and branch is not None:
        # get all the builds
        build_files = [f for f in os.listdir(build_dir) if os.path.isfile(os.path.join(build_dir, f))]

        for build_file in build_files:
            # if the request build already exists
            if build_file.split('_')[1] == branch and build_file.split('_')[2] == commit:
                return build_file
        else:
            latest_build_path = command_line_build(repo_path, project_name, branch, commit, build_dir)
            return latest_build_path
    else:
        repo = Repo(repo_path)
        branch = repo.active_branch.name
        commit = repo.head.commit.hexsha[:7]
        latest_build_path = command_line_build(repo_path, project_name, branch, commit, build_dir)
        return latest_build_path

def command_line_build(repo_path, project_name, branch, commit, build_dir):
    """ Performs the command line build of the npm project """
    # Switch to the repo
    os.chdir(repo_path)

    repo = Repo(repo_path)
    if branch is not None:
        repo.git.checkout(branch)
    if commit is not None:        
        repo.git.checkout(commit)

    # Ensure that we are in the repo
    os.chdir(repo_path)

    # run the install & build commands
    os.system("npm install")
    os.system("npm run build")

    # package the build as tar
    tar_filename = f"{project_name}_{branch}_{commit}.tar"
    tar_path = os.path.join(build_dir, tar_filename)
    with tarfile.open(tar_path, "w") as tar:
        tar.add("build", arcname="build")

    return tar_path

def deploy_project(latest_build_name, repo_path, project_name, branch=None, commit=None):
    temp_dir = os.path.join(repo_path, '.delfx', 'build')
    os.chdir(temp_dir)

    upload_payload = {
        'project_name': project_name,
        'user_id': user_id,
    }
    headers = {
        'Authroization': f'Bearer {CLIENT_API_KEY}',
        'User-Token': user_jwt_token,
    }
    
    latest_build = os.path.join(temp_dir, latest_build_name)
    files = {'file': open(latest_build, 'rb')}
    response = requests.post(UPLOAD_ENDPOINT, data=upload_payload, files=files, headers=headers)

    if response.status_code == 201:
        return
    else:
        print("Failed to deploy the app to deployment server")

def login_user(email, password):
    """ User Login API request """
    login_payload = {
        'email': email,
        'password': password
    }
    headers = {'Authroization': f'Bearer {CLIENT_API_KEY}'}

    response = requests.post(AUTH_API_ENDPOINT, data=login_payload, headers=headers)

    if response.status_code == 200:
        print("Login successful.")
        user_id = response.json().get('user_id')
        user_jwt_token = response.json().get('token')
        return user_id, user_jwt_token
    else:
        print(f"Login failed. Status code : {response.status_code}")

def command_line_login():
    """ Performs command line login """
    email = input("Enter your email: ")
    password = getpass.getpass("Enter your password: ")

    try:
        user_id, jwt_token = login_user(email, password)

        if user_id and jwt_token:
            store_user(user_id, jwt_token)
            return user_id, jwt_token
        else:
            print("Login unsuccessful. Exiting.")
            return None
    except Exception as ex:
        print(f"Error : {ex}")
    
def store_user(user_id, jwt_token):
    """ Stores the user_id and jwt_token in a creds file """
    user_cred_file = os.path.join(system_temp_dir, 'user_creds.creds')
    with open(user_cred_file, 'w') as creds:
        creds.write(f"{user_id}:{jwt_token}")

def load_user():
    """ Loads the user_id and jwt_token from the creds file """
    user_cred_file = os.path.join(system_temp_dir, 'user_creds.creds')
    with open(user_cred_file, 'r') as creds:
        user_cred = creds.read()
    user_id = user_cred.split(':')[0]
    user_jwt_token = user_cred.split(':')[1]
    
def get_npm_project_name(project_path):
    try:
        package_json_path = os.path.join(project_path, 'package.json')

        with open(package_json_path, 'r') as package_json:
            data = json.load(package_json_path)
            project_name = data.get('name')
            return project_name
    except Exception as ex:
        print(f"Error : {ex}")
        return None
    

description = f"""
Command Line utility for Delta Functions

Commands:

    login   - Login to Delta Fx (Command Line)
    init    - Initializes an Empty Delta Fx project
    build   - Build the projet
    deploy  - Deploy the project on Delta Fx

Please login to Delta Fx to deploy projects and manage projects
"""

def main():
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("command", help="Command to perform")

    parser.add_argument("project_path", help="Path to the project folder")
    parser.add_argument("branch", help="The branch to build")
    parser.add_argument("commit", help="The commit to build")

    args = parser.parse_args()

    latest_build_filename = ''

    if args.command == 'init':
        if args.project_path:
            init_project(args.project_path)
        else:
            init_project(os.getcwd())
    elif args.command == 'build':
        if args.project_path:
            project_path = args.project_path
        else:
            project_path = os.getcwd()
        project_name = get_npm_project_name(project_path)
        latest_build_filename = build_project(repo_path=project_path, project_name=project_name)

    elif args.command == 'login':
        command_line_login()
    elif args.command == 'deploy':
        if args.project_path:
            project_path = args.project_path
        else:
            project_path = os.getcwd()
        project_name = get_npm_project_name(project_path)
        deploy_project(latest_build_name=latest_build_filename, repo_path=project_path, project_name=project_name, branch=args.branch, commit=args.commit)


if __name__ == "__main__":
    command_line_login()