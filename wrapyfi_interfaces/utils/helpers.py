
def str_or_int(arg):
    try:
        return int(arg)  # try convert to int
    except ValueError:
        return arg

