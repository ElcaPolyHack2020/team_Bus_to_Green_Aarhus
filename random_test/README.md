# Random Test
This is a little test project I created that generates random cityscapes with car and passenger traffic. This might help as a "clean" benchmark for measuring our algorithms performance.

## Usage
Generate a new random map:
```
./generate.sh
```

Run the experiment:
```
python3 runner.py
```

## Folders
- [data](data)
    The randomly generated city data from `generate.sh`
- [extra](extra)
    Extra things such as a list of first and last names that help memorize passenger ids better.