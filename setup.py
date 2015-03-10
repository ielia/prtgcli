from setuptools import setup

setup(
    name='prtgcli',
    version='0.0.1',
    description='A PRTG Commandline Tool',
    url='http://github.com/kevinschoon/prtg-py',
    author='Kevin Schoon',
    author_email='kevinschoon@gmail.com',
    maintainer='Kevin Schoon',
    maintainer_email='kevinschoon@gmail.com',
    keywords=['PRTG', 'Network Monitoring'],
    license='MIT',
    packages=['prtgcli'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    entry_points={'console_scripts': ['prtg = prtgcli.cli:main']},
    setup_requires=[
        'PyYAML',
        'prettytable',
        'prtg-py'
    ],
    test_suite='tests'
)
