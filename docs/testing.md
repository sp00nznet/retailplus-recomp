# Testing

## The conformance harness

```
py -3 tools\pos_diff.py              # both, compared
py -3 tools\pos_diff.py --only orig  # just the original
```

Each program gets a fresh copy of `game\` in a temporary folder and runs on a
hidden desktop of its own (nothing shows on your screens; it works over RDP).
The same script drives both through window messages:

1. **Add a product.** File > Inventory > Open, Edit > Add Item: a STANDARD
   item `RPX1`, "RECOMP TEST WIDGET", price 12.34, 5 in stock, cost 6.00.
2. **Ring up a sale.** File > Point Of Sale, Start, scan `RPX1`, quantity 2,
   Total, Save (cash, no receipt printer).
3. **Export.** Inventory > Tools > Export Inventory to `EXPORT.CSV`.

Then it compares every DBF's rows (the inventory, the sales log `SALES001`,
the day's totals `TOTAL001`, the transaction log, setup, numbering, staff)
and the export, and prints `IDENTICAL` or `DIFFERENT` for each. The time of
day of the sale is masked; both runs are on the same day. Without
`game\PLUSLITE.EXE` it prints `skipped` and exits 0.

On the original the export shows the script worked: the new item with 3 left
in stock, 2 sold, 24.68 taken.


Current result: 11 of 11 IDENTICAL.
