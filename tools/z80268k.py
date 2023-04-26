import re,itertools,os,collections
import argparse
import simpleeval # get it on pypi (pip install simpleeval)

parser = argparse.ArgumentParser()
parser.add_argument("input_file")
parser.add_argument("output_file")

args = parser.parse_args()
if os.path.abspath(args.input_file) == os.path.abspath(args.output_file):
    raise Exception("Define an output file which isn't the input file")




regexes = []
##for s,r in regexes_1:
##    try:
##        regexes.append((re.compile(s,re.IGNORECASE|re.MULTILINE),r))
##    except re.error as e:
##        raise Exception("{}: {}".format(s,e))

address_re = re.compile("([0-9A-F]{4}):")
# doesn't capture all hex codes properly but we don't care
instruction_re = re.compile("([0-9A-F]{4}):( [0-9A-F]{2}){1,}\s+(\S.*)")

address_lines = {}
lines = []
with open(args.input_file) as f:
    for line in f:
        m = instruction_re.match(line)
        is_inst = False
        if m:
            address = int(m.group(1),0x10)
            instruction = m.group(3)
            address_lines[address] = instruction
            txt = instruction.rstrip()
            is_inst = True
        else:
            txt = line.rstrip()
        lines.append((txt,is_inst))

# convention:
# a => d0
# b => d1
# c => d2
# ix => a2
# iy => a3
# and (free use as most of the time there are specifics
# with d and e which make de same for h & l.
# d => d3
# e => d4  (manual rework required!)
# h => d5 or a0 for hl
# l => d6 (manual rework required!)

registers = {
"a":"d0","b":"d1","c":"d2","ix":"a2","iy":"a3","hl":"a0","de":"a1"}  #,"d":"d3","e":"d4","h":"d5","l":"d6",

a_instructions = {"neg":"neg.b","not":"not.b","rra":"asr.b",
                    "rla":"asl.b","rrca":"roxr.b\t#1,","rlca":"roxl.b\t#1,"}
single_instructions = {"ret":"rts"}

m68_regs = set(registers.values())
m68_data_regs = {x for x in m68_regs if x[0]=="d"}
m68_address_regs = {x for x in m68_regs if x[0]=="a"}

# inverted
rts_cond_dict = {"d2":"bcc","nc":"bcs","z":"bne","nz":"beq","p":"bmi","m":"bpl","po":"bvc","pe":"bvs"}
# d2 stands for c which has been replaced in a generic pass
jr_cond_dict = {"d2":"jcs","nc":"jcc","z":"jeq","nz":"jne","p":"jpl","m":"jmi","po":"jvs","pe":"jvc"}

out_lines = []

def f_djnz(args,address,comment):
    target_address = int(args[0],16)
    # a dbf wouldn't work as d1 loaded as byte and with 1 more iteration
    # adapt manually if needed
    return f"\tsubq.b\t#1,d1\n\tjne\tl_{target_address:04x}\t{comment}"


def f_bit(args,address,comment):
    return f"\tbtst.b\t#{args[0]},{args[1]}{comment}"

def f_xor(args,address,comment):
    arg = args[0]
    if arg=="d0":
        return f"\tmoveq\t#0,d0{comment}"
    return f"\teor.b\t{arg},d0{comment}"

def f_ret(args,address,comment):
    binst = rts_cond_dict[args[0]]
    return f"\t{binst}.b\t0f\n\trts{comment}\n0:"

def f_jp(args,address,comment):
    if len(args)==1:
        address = int(args[0],16)
        out = f"\tjra\tl_{address:04x}{comment}"
    else:
        jinst = jr_cond_dict[args[0]]
        address = int(args[1],16)
        out = f"\t{jinst}\tl_{address:04x}{comment}"
    return out

def f_and(args,address,comment):
    p = args[0]
    out = None
    if p == "d0":
        out = f"\ttst.b\td0{comment}"
    elif p in m68_regs:
        out = f"\tand.b\t{p},d0{comment}"
    elif p.startswith("0x"):
        out = f"\tand.b\t#{p},d0{comment}"
    return out

def f_add(args,address,comment):
    dest = args[0]
    source = args[1]
    out = None
    if dest in m68_address_regs:
        # not supported
        return

    if source in m68_regs:
        out = f"\t{inst}.b\t{source},{dest}{comment}"
    elif source.startswith("0x"):
        if int(source,16)<8:
            out = f"\taddq.b\t#{source},{dest}{comment}"
        else:
            out = f"\tadd.b\t#{source},{dest}{comment}"
    else:
        out = f"\tadd.b\t{source},{dest}{comment}"
    return out

def f_sub(args,address,comment):
    dest = "d0"
    source = args[0]
    out = None
    if source in m68_regs:
        out = f"\tsub.b\t{source},{dest}{comment}"
    elif source.startswith("0x"):
        if int(source,16)<8:
            out = f"\tsubq.b\t#{source},{dest}{comment}"
        else:
            out = f"\tsub.b\t#{source},{dest}{comment}"
    else:
        out = f"\tsub.b\t{source},{dest}{comment}"
    return out

def gen_addsub(args,address,comment,inst):
    dest = args[0]
    source = args[1] if len(args)==2 else "d0"
    out = None
    if source in m68_regs:
        out = f"\t{inst}.b\t{source},{dest}{comment}"
##    elif p.startswith("0x"):
##        if int(p,16)<8:
##            out = f"\t{inst}q.b\t#{p},d0{comment}"
##        else:
##            out = f"\t{inst}.b\t#{p},d0{comment}"
    return out

def address_to_label(s):
    return s.strip("()").replace("0x","l_")

def f_or(args,address,comment):
    p = args[0]
    out = None
    if p in m68_regs:
        out = f"\tor.b\t{p},d0{comment}"
    elif p.startswith("0x"):
        out = f"\tor.b\t#{p},d0{comment}"
    return out

def f_cp(args,address,comment):
    p = args[0]
    out = None
    if p in m68_regs:
        out = f"\tcmp.b\t{p},d0{comment}"
    elif p.startswith("0x"):
        out = f"\tcmp.b\t#{p},d0{comment}"
    return out

def f_dec(args,address,comment):
    p = args[0]
    out = None
    if p in m68_data_regs:
        out = f"\tsubq.b\t#1,{p}{comment}"
    return out

def f_inc(args,address,comment):
    p = args[0]
    out = None
    if p in m68_data_regs:
        out = f"\taddq.b\t#1,{p}{comment}"
    return out

def f_ld(args,address,comment):
    dest,source = args[0],args[1]
    out = None
    if dest in m68_regs:
        if source.startswith("("):
            # direct addressing
            prefix = ""
            srclab = source.strip("()")
            if srclab not in m68_address_regs:
                source = address_to_label(source)
        else:
            prefix = "#"
        if dest[0]=="a":
            source = address_to_label(source)
            out = f"\tlea\t{source}(pc),{dest}{comment}"
        else:
            out = f"\tmove.b\t{prefix}{source},{dest}{comment}"
    elif dest.startswith("("):
        destlab = dest.strip("()")
        if destlab not in m68_address_regs:
            dest = address_to_label(dest)

        prefix = ""
        if source.startswith("0x"):
            prefix = "#"
        out = f"\tmove.b\t{prefix}{source},{dest}{comment}"


    return out

f_jr = f_jp


converted = 0

for i,(l,is_inst) in enumerate(lines):
    out = ""
    if is_inst:
        # try to convert
        toks = l.split("|",maxsplit=1)
        comment = "" if len(toks)==1 else f"\t\t|{toks[1]}"
        # add original z80 instruction
        if not comment:
            comment = "\t\t|"
        inst = toks[0].strip()
        comment += f" [{inst}]"
        itoks = inst.split()
        if len(itoks)==1:
            # single instruction either towards a or without argument
            ai = a_instructions.get(inst)
            if ai:
                out = f"\t{ai}d0{comment}"
            else:
                si = single_instructions.get(inst)
                if si:
                    out = f"\t{si}{comment}"
        else:
            inst = itoks[0]
            args = itoks[1:]
            # other instructions, not single, not implicit a
            conv_func = globals().get(f"f_{inst}")
            if conv_func:
                jargs = args[0].split(",")
                # switch registers now
                jargs = [re.sub(r"\b(\w+)\b",lambda m:registers.get(m.group(1),m.group(1)),a) for a in jargs]
                # replace "+" for address registers and swap params
                jargs = [re.sub("\((a\d)\+(0x\d+)\)",r"(\2,\1)",a) for a in jargs]
                out = conv_func(jargs,address,comment)
    else:
        out=address_re.sub(r"l_\1:",l)
        # convert tables like xx yy aa bb with .byte
        out = re.sub(r"\s+([0-9A-F][0-9A-F])\b",r",0x\1",out)
        out = out.replace(":,",":\n\t.byte\t")
    if out:
        converted += 1
    else:
        out = l
    print(out)
    out_lines.append(out)

print(f"converted ratio {converted}/{len(lines)} {int(100*converted/len(lines))}%")





