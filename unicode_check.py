s = "Magic: The Gathering: Untold Stories―Elspeth"
for c in s:
    if ord(c) > 127:
        print(f"{c}: {ord(c)} (hex: {hex(ord(c))})")
