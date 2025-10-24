"""
Сервіс для експорту даних
"""

import io
import logging
from datetime import datetime
from typing import List, Dict
import pandas as pd
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors

from app.config.settings import config

logger = logging.getLogger(__name__)


class ExportService:
    """Сервіс для експорту даних у різні формати"""
    
    @staticmethod
    def export_to_csv(transactions: List[Dict]) -> io.BytesIO:
        """Експортує транзакції в CSV"""
        df = pd.DataFrame(transactions)
        
        # Очищаємо та форматуємо дані
        if not df.empty:
            df = df[['date', 'amount', 'category', 'note', 'balance', 'currency']]
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d %H:%M')
        
        buffer = io.BytesIO()
        df.to_csv(buffer, index=False, encoding='utf-8-sig')
        buffer.seek(0)
        
        logger.info(f"Exported {len(transactions)} transactions to CSV")
        return buffer
    
    @staticmethod
    def export_to_excel(transactions: List[Dict]) -> io.BytesIO:
        """Експортує транзакції в Excel"""
        df = pd.DataFrame(transactions)
        
        if not df.empty:
            df = df[['date', 'amount', 'category', 'note', 'balance', 'currency']]
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Перейменовуємо колонки українською
            df.columns = ['Дата', 'Сума', 'Категорія', 'Опис', 'Баланс', 'Валюта']
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Транзакції', index=False)
            
            # Автоматична ширина колонок
            worksheet = writer.sheets['Транзакції']
            for idx, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = max_length
        
        buffer.seek(0)
        logger.info(f"Exported {len(transactions)} transactions to Excel")
        return buffer
    
    @staticmethod
    def export_to_pdf(transactions: List[Dict], nickname: str, balance: float, currency: str) -> io.BytesIO:
        """Експортує транзакції в PDF з красивим форматуванням"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Заголовок
        title = Paragraph(f"<b>Фінансовий звіт: {nickname}</b>", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Інфо про баланс
        balance_text = Paragraph(
            f"<b>Поточний баланс:</b> {balance:.2f} {currency}<br/>"
            f"<b>Дата звіту:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles['Normal']
        )
        elements.append(balance_text)
        elements.append(Spacer(1, 20))
        
        # Таблиця транзакцій
        if transactions:
            data = [['Дата', 'Сума', 'Категорія', 'Опис']]
            
            for t in transactions:
                date = datetime.fromisoformat(t['date']).strftime('%Y-%m-%d %H:%M')
                amount = f"{t['amount']:.2f}"
                category = t['category']
                note = t['note'][:30] + '...' if len(t['note']) > 30 else t['note']
                data.append([date, amount, category, note])
            
            table = Table(data, colWidths=[120, 70, 100, 200])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
        
        doc.build(elements)
        buffer.seek(0)
        
        logger.info(f"Exported {len(transactions)} transactions to PDF")
        return buffer


# Singleton
export_service = ExportService()