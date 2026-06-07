import time

def datetime_now():
    ''' Return string with year, month, day, hour, minute, second '''
    return time.strftime("%Y_%m_%d_%H_%M_%S_%Z")
