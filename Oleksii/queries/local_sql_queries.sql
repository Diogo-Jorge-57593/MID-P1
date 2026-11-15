-- =====================================================================
-- DMI Project P1: Local Queries for Subtopic 1 (Venture Capital)
-- Database: PostgreSQL
-- =====================================================================

-- Query 1 (Intermediate Level): 
-- Retrieve the names of startups, their sectors, the investor funds, 
-- and the investment amounts, filtered strictly for late-stage deals 
-- (Series A and Series B), ordered by investment size.

SELECT 
    s.company_name, 
    s.sector, 
    i.fund_name, 
    f.round_type, 
    f.investment_amount
FROM startups s
JOIN funding_rounds f ON s.startup_id = f.startup_id
JOIN investors i ON f.investor_id = i.investor_id
WHERE f.round_type IN ('Series A', 'Series B')
ORDER BY f.investment_amount DESC;


-- Query 2 (Complex Level): 
-- Aggregate total investments and count the number of unique funded 
-- startups grouped by sector, displaying only sectors that have 
-- received more than $10,000,000 in total funding.

SELECT 
    s.sector, 
    COUNT(DISTINCT s.startup_id) AS total_startups, 
    SUM(f.investment_amount) AS total_invested_usd
FROM startups s
LEFT JOIN funding_rounds f ON s.startup_id = f.startup_id
GROUP BY s.sector
HAVING SUM(f.investment_amount) > 10000000
ORDER BY total_invested_usd DESC;