#!/usr/bin/env python3
"""
Faithful simulation of canvas-editor 1.0.6
TableParticle.computeRowColInfo (src/editor/core/draw/particle/table/TableParticle.ts:681)
to locate the cell that makes `colgroup[col + colIndex]` out of range.

Usage: python3 sim_colindex.py /tmp/probe_tables.json
"""
import json
import sys


def get_td_list_by_col_index(tr_list, col_index):
    out = []
    for tr in tr_list:
        for td in tr['tdList']:
            mn = td['colIndex']
            mx = mn + td['colspan'] - 1
            if col_index >= mn and col_index <= mx:
                out.append(td)
    return out


def get_row_count_by_col_index(tr_list, col_index):
    return sum(td['rowspan'] for td in get_td_list_by_col_index(tr_list, col_index))


def compute_row_col_info(table, verbose=False):
    """Returns (ok, message). Mutates table['trList'][*]['tdList'][*]['colIndex']."""
    colgroup = table['colgroup']
    tr_list = table['trList']
    if not colgroup or not tr_list:
        return True, 'no colgroup/trList -> early return'
    for t, tr in enumerate(tr_list):
        td_list = tr['tdList']
        for d, td in enumerate(td_list):
            col_index = 0
            if len(tr_list) > 1 and t != 0:
                pre_td = td_list[d - 1] if d > 0 else None
                start = (pre_td['colIndex'] + pre_td['colspan']) if pre_td else d
                for c in range(start, len(colgroup)):
                    row_count = get_row_count_by_col_index(tr_list[:t], c)
                    if row_count == t:
                        col_index = c
                        break
            else:
                pre_td = td_list[d - 1] if d > 0 else None
                if pre_td:
                    col_index = pre_td['colIndex'] + pre_td['colspan']

            # crash site: TableParticle.ts:724
            for col in range(td['colspan']):
                idx = col + col_index
                if idx >= len(colgroup) or idx < 0:
                    return False, (
                        f"colgroup[{idx}] is undefined  "
                        f"(table depth={table['depth']}, trIndex={t}, tdIndex={d}, "
                        f"colIndex={col_index}, colspan={td['colspan']}, "
                        f"colgroup.length={len(colgroup)}, text={td['text']!r})"
                    )
            # tail of the real routine
            td['colIndex'] = col_index
    return True, 'ok'


def main():
    probe = json.load(open(sys.argv[1]))
    for table in probe['tables']:
        print(f"=== table depth={table['depth']} colgroup={[c['width'] for c in table['colgroup']]}")
        for p in (1, 2):
            ok, msg = compute_row_col_info(table)
            print(f"  pass {p}: {msg}")
            if not ok:
                print("  >>> CRASH")
                # show the state of the table at the failing point
                for ri, tr in enumerate(table['trList']):
                    print("     row", ri, [
                        (c['colIndex'], c['colspan'], c['rowspan'], c['text'][:18])
                        for c in tr['tdList']
                    ])
                return
        print("  (both passes ok)")


if __name__ == '__main__':
    main()
