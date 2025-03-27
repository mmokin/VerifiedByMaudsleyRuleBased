# set up basic requirements for droidbot and Verified by Maudsley
from setuptools import setup, find_packages, findall
import os

setup(
    name='AutoDroid',
    packages=find_packages(include=['droidbot', 'droidbot.adapter', 'VerifiedByMaudsley', 'VerifiedByMaudsley.assessment']),
    # this must be the same as the name above
    version='1.0.3',
    description='A lightweight UI-guided test input generator for Android with mental health app assessment capabilities.',
    author='DroidBot Team and Maudsley Contributors',
    license='MIT',
    url='https://github.com/honeynet/droidbot',
    keywords=['testing', 'monkey', 'exerciser', 'mental health', 'ui assessment'],
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here
        'Programming Language :: Python :: 3',
    ],
    entry_points={
        'console_scripts': [
            'droidbot=droidbot.start:main',
            'verified-maudsley=VerifiedByMaudsley.run_assessment:main',
        ],
    },
    package_data={
        'droidbot': [os.path.relpath(x, 'droidbot') for x in findall('droidbot/resources/')],
        'VerifiedByMaudsley': ['config.json', '*.bat']
    },
    # Added new dependencies for Verified by Maudsley project
    install_requires=[
        'androguard>=3.4.0a1',
        'networkx',
        'Pillow',
        'requests',
        'pyvis',
        'treelib',
        'pyyaml',
        'torch',
        'InstructorEmbedding',
        'sentence_transformers',
        'pytesseract',
        'openai',
        'telnetlib3',
        'scikit-learn',
        'numpy',
        'opencv-python',
        'jinja2'
    ],
)