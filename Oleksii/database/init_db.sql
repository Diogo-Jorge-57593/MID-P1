-- 1. Создаем таблицу Инвесторов (Венчурных фондов)
CREATE TABLE investors (
    investor_id SERIAL PRIMARY KEY,
    fund_name VARCHAR(255) NOT NULL,
    capital_volume DECIMAL(15, 2),
    headquarters VARCHAR(100)
);

-- 2. Создаем таблицу Стартапов
CREATE TABLE startups (
    startup_id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    sector VARCHAR(100),
    jurisdiction VARCHAR(100),
    founded_year INT
);

-- 3. Создаем таблицу Раундов финансирования (связующая таблица)
CREATE TABLE funding_rounds (
    round_id SERIAL PRIMARY KEY,
    startup_id INT REFERENCES startups(startup_id),
    investor_id INT REFERENCES investors(investor_id),
    round_type VARCHAR(50),
    investment_amount DECIMAL(15, 2),
    round_date DATE
);


-- Добавляем инвестора
INSERT INTO investors (fund_name, capital_volume, headquarters)
VALUES ('Sequoia Capital', 85000000000.00, 'USA');

-- Добавляем стартап
INSERT INTO startups (company_name, sector, jurisdiction, founded_year)
VALUES ('AI Analytics Corp', 'Artificial Intelligence', 'Portugal', 2024);

-- Добавляем информацию о раунде инвестиций (связываем стартап №1 и инвестора №1)
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date)
VALUES (1, 1, 'Seed', 1500000.00, '2026-03-15');

SELECT * FROM funding_rounds;

-- 1. Вставляем инвесторов
INSERT INTO investors (investor_id, fund_name, capital_volume, headquarters) VALUES (1, 'Andreessen Horowitz', 450000000, 'UK') ON CONFLICT (investor_id) DO NOTHING;
INSERT INTO investors (investor_id, fund_name, capital_volume, headquarters) VALUES (2, 'Index Ventures', 53000000, 'UK') ON CONFLICT (investor_id) DO NOTHING;
INSERT INTO investors (investor_id, fund_name, capital_volume, headquarters) VALUES (3, 'Sequoia Capital', 95000000, 'UK') ON CONFLICT (investor_id) DO NOTHING;
INSERT INTO investors (investor_id, fund_name, capital_volume, headquarters) VALUES (4, 'AI Capital', 329000000, 'UK') ON CONFLICT (investor_id) DO NOTHING;
INSERT INTO investors (investor_id, fund_name, capital_volume, headquarters) VALUES (5, 'Highland Europe', 153000000, 'UK') ON CONFLICT (investor_id) DO NOTHING;
INSERT INTO investors (investor_id, fund_name, capital_volume, headquarters) VALUES (6, 'Tech Ventures', 357000000, 'UK') ON CONFLICT (investor_id) DO NOTHING;
INSERT INTO investors (investor_id, fund_name, capital_volume, headquarters) VALUES (7, 'Seed Capital', 320000000, 'UK') ON CONFLICT (investor_id) DO NOTHING;
INSERT INTO investors (investor_id, fund_name, capital_volume, headquarters) VALUES (8, 'Future Fund', 204000000, 'UK') ON CONFLICT (investor_id) DO NOTHING;
INSERT INTO investors (investor_id, fund_name, capital_volume, headquarters) VALUES (9, 'Innovation Partners', 225000000, 'UK') ON CONFLICT (investor_id) DO NOTHING;
INSERT INTO investors (investor_id, fund_name, capital_volume, headquarters) VALUES (10, 'Google Ventures', 80000000, 'UK') ON CONFLICT (investor_id) DO NOTHING;

-- 2. Вставляем стартапы
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (1, 'Itoflow', 'AI', 'UK', 2023) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (2, 'Embedd', 'Energy', 'UK', 2020) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (3, 'Prevalent AI', 'Fintech', 'UK', 2019) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (4, 'UKRI', 'Energy', 'UK', 2019) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (5, 'Callosum', 'Energy', 'UK', 2018) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (6, 'AI tutor startup Medly', 'Cybersecurity', 'UK', 2019) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (7, 'Noggin HQ', 'Space Tech', 'UK', 2020) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (8, 'Ampaire', 'AI', 'UK', 2022) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (9, 'AI Growth Zone', 'Fintech', 'UK', 2024) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (10, 'GALLOS Technologies', 'Energy', 'UK', 2022) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (11, 'Mindgard', 'Space Tech', 'UK', 2018) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (12, 'M&A advisory LAVA', 'AI', 'UK', 2018) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (13, 'Cytix', 'Space Tech', 'UK', 2023) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (14, 'FlairMakers', 'Space Tech', 'UK', 2018) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (15, 'Watercycle Technologies', 'AI', 'UK', 2018) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (16, 'Edgify', 'Energy', 'UK', 2019) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (17, 'Vertical Aerospaces', 'Fintech', 'UK', 2019) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (18, 'Aerospace', 'Space Tech', 'UK', 2022) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (19, 'Mironid', 'Energy', 'UK', 2019) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (20, 'Index Ventures', 'Fintech', 'UK', 2023) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (21, 'Intropy', 'Fintech', 'UK', 2024) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (22, 'Kinematic Trees', 'Fintech', 'UK', 2023) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (23, 'TaskHer', 'Fintech', 'UK', 2023) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (24, 'Social Investment Scotland', 'Cybersecurity', 'UK', 2023) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (25, 'Agon', 'Space Tech', 'UK', 2020) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (26, 'LemonEdge', 'AI', 'UK', 2021) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (27, 'Qureight', 'Cybersecurity', 'UK', 2019) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (28, 'Dwelly', 'Energy', 'UK', 2024) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (29, 'iwoca', 'Energy', 'UK', 2024) ON CONFLICT (startup_id) DO NOTHING;
INSERT INTO startups (startup_id, company_name, sector, jurisdiction, founded_year) VALUES (30, 'Nuclear Turbines', 'Fintech', 'UK', 2023) ON CONFLICT (startup_id) DO NOTHING;

-- 3. Вставляем раунды финансирования
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (1, 7, 'Series B', 1800000.0, '2026-09-10');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (2, 5, 'Pre-seed', 2000000.0, '2026-11-07');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (3, 2, 'Series B', 16100000.00, '2026-09-08');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (4, 5, 'Series B', 28000000.0, '2026-09-02');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (5, 3, 'Seed', 73500000.0, '2026-08-26');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (6, 2, 'Seed', 6000000.0, '2026-10-22');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (7, 5, 'Series A', 2300000.0, '2026-06-21');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (8, 2, 'Seed', 14000000.0, '2026-10-13');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (9, 10, 'Series B', 300000000.0, '2026-06-04');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (10, 8, 'Seed', 35000000.0, '2026-08-09');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (11, 5, 'Series A', 22000000.0, '2026-08-07');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (12, 4, 'Series B', 8000000.0, '2026-10-15');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (13, 9, 'Series A', 5000000.0, '2026-10-04');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (14, 8, 'Series A', 500000.0, '2026-08-07');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (15, 9, 'Series B', 3000000.0, '2026-09-14');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (16, 2, 'Pre-seed', 6700000.0, '2026-06-25');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (17, 8, 'Seed', 74000000.0, '2026-06-18');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (18, 1, 'Pre-seed', 222000000.0, '2026-06-18');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (19, 8, 'Series A', 34000000.0, '2026-08-26');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (20, 6, 'Series B', 1500000000.0, '2026-06-06');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (21, 3, 'Seed', 8170000.0, '2026-09-25');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (22, 7, 'Series B', 585000.0, '2026-06-25');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (23, 9, 'Series A', 650000.0, '2026-07-01');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (24, 9, 'Seed', 3500000.0, '2026-11-05');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (25, 9, 'Seed', 22500000.0, '2026-10-11');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (26, 3, 'Pre-seed', 15800000.0, '2026-06-12');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (27, 8, 'Series A', 15000000.0, '2026-08-26');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (28, 5, 'Series A', 128000000.0, '2026-07-20');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (29, 9, 'Series A', 250000000.0, '2026-08-07');
INSERT INTO funding_rounds (startup_id, investor_id, round_type, investment_amount, round_date) VALUES (30, 8, 'Series B', 15000000.0, '2026-09-06');