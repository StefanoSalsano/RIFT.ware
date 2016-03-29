#!/usr/bin/env python3

import sys
import os                                                           

d={}
with open("./templates/trafgen_2VM") as fd:
    s = [line.strip().split(None, 1) for line in fd]
    print("S0 %s" % s[0])
    print("S1 %s" % s[1])
    for l in s:
      print(l[1])
      j = [k.strip().split("=", -1) for k in l[1].strip().split(",",-1)]
      print(j)
#      m=dict(j)
#      h=dict(l[1].split("=",1).split(",",10))
#      for keys,values in h.items():
#        print(keys)
#        print(values)
      print(s[0])
      d[l[0]] = dict(j)
for keys,values in d.items():
    print(keys)
    print(values)
print(d)
try:
  p=d['RW.VM.FASTPATH.LLEAD']
  print(p)
  print(p['external_port'])
except  KeyError:
  print("Element not found");
