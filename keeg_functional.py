# Misc collection of functional programming tools 
# so that I don't go insane while using python

import copy

def first(f,l):
    for e in l:
        if f(e):
            return e
    return None

def drop_while(f,l):
    if l == []:
        return l

    if f(l[0]):
        return drop_while(f,l[1:])
    else:
        return l

def take_while(f,l):
    results = []
    for e in l:
        if f(e):
            results.append(e)
        else:
            return results
    return results

# Take a value, pass it to a function, pass the result to the next function,
# and so on, until the end of the "pipe" of functions. 
# Sort of a left-to-right function composition, if you've used haskell
def pipe(start_val, fs):
    v = fs[0](start_val)
    for f in fs[1:]:
        v = f(v)
    return v

# partially evaluate function f with value v
def p(f,x):
    return lambda y: f(x,y)
