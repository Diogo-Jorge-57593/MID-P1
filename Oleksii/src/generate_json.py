import json
import random
import os
from datetime import datetime, timedelta

# Создаем папку для второго источника данных
output_dir = "json_metrics"
os.makedirs(output_dir, exist_ok=True)

# Генерируем метрики для 30 стартапов, которые лежат в PostgreSQL
for startup_id in range(1, 31):
    metrics = {
        "startup_reference_id": startup_id,
        "currency": "USD",
        "monthly_reports": []
    }
    
    # Генерируем данные за последние 3 месяца
    base_mrr = random.uniform(10000, 500000)
    
    for i in range(3):
        # Намеренно делаем формат даты строкой (для конфликта гетерогенности с DATE в SQL)
        report_month = (datetime(2026, 11, 1) - timedelta(days=30*i)).strftime("%B %Y")
        
        # Немного меняем MRR от месяца к месяцу
        current_mrr = base_mrr * random.uniform(0.9, 1.2)
        
        report = {
            "month": report_month,
            "financials": {
                "mrr": round(current_mrr, 2),
                "cac": round(random.uniform(500, 5000), 2),
                "churn_rate_pct": round(random.uniform(1.0, 8.5), 2)
            }
        }
        metrics["monthly_reports"].append(report)
        
    # Сохраняем в файл
    filename = os.path.join(output_dir, f"startup_{startup_id}_kpi.json")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=4)

print(f"Успешно сгенерировано 30 JSON файлов в папке {output_dir}/")