# SQL: joins, groups and missing values
A LEFT JOIN retains every row of the left input. If no right row matches its ON condition, the right-side columns in that output row are NULL. A WHERE condition on a right-side column can remove these unmatched rows: equality comparisons involving NULL do not evaluate to true. Filtering the right input in the ON condition can therefore differ from filtering the joined result in WHERE.

WHERE filters input rows before grouping. GROUP BY forms groups, and HAVING filters groups after aggregation. To count all purchases per customer but keep only customers with at least two purchases, group by customer and put the aggregate condition in HAVING.

COUNT(*) counts rows; COUNT(column) counts rows whose value in that column is not NULL. Following a LEFT JOIN, COUNT(*) can include a retained unmatched row while COUNT(right.id) is zero for that customer. Use IS NULL to test for missing values, not equality to NULL.
