from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, desc, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
import matplotlib.pyplot as plt
import seaborn as sns
import io
import calendar
import pandas as pd
import os


SQLALCHEMY_DATABASE_URL ="sqlite:///./expenses.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class ExpenseDB(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float)
    category = Column(String)
    date = Column(Date)
    description = Column(String)

Base.metadata.create_all(bind=engine)

# Pydantic models
class ExpenseBase(BaseModel):
    amount: float
    category: str
    date: date
    description: str

class ExpenseCreate(ExpenseBase):
    pass

class Expense(ExpenseBase):
    id: int

    class Config:
        orm_mode = True

# Get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

# CRUD operations
@app.post("/expenses/", response_model=Expense)
def create_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    db_expense = ExpenseDB(**expense.model_dump())
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.get("/expenses/", response_model=List[Expense])
def read_expenses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # expenses = db.query(ExpenseDB).offset(skip).limit(limit).all()
    expenses = db.query(ExpenseDB).order_by(desc(ExpenseDB.date)).offset(skip).limit(limit).all()
    return expenses

@app.get("/expenses/{expense_id}", response_model=Expense)
def read_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(ExpenseDB).filter(ExpenseDB.id == expense_id).first()
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense

@app.put("/expenses/{expense_id}", response_model=Expense)
def update_expense(expense_id: int, expense: ExpenseCreate, db: Session = Depends(get_db)):
    db_expense = db.query(ExpenseDB).filter(ExpenseDB.id == expense_id).first()
    if db_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    for key, value in expense.model_dump().items():
        setattr(db_expense, key, value)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.delete("/expenses/{expense_id}", response_model=Expense)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(ExpenseDB).filter(ExpenseDB.id == expense_id).first()
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return expense

# Charts
@app.get("/charts/yearly_expense_line/{year}")
def yearly_expense_line_chart(year: int, db: Session = Depends(get_db)):
    expenses = db.query(
        func.extract('month', ExpenseDB.date).label('month'),
        func.sum(ExpenseDB.amount).label('total')
    ).filter(
        func.extract('year', ExpenseDB.date) == year
    ).group_by(
        func.extract('month', ExpenseDB.date)
    ).order_by('month').all()
    
    df = pd.DataFrame([(e.month, e.total) for e in expenses], columns=['month', 'total'])
    df['month'] = df['month'].apply(lambda x: calendar.month_abbr[int(x)])
    
    plt.figure(figsize=(12, 6))
    sns.set_style("white")
    sns.lineplot(x='month', y='total', data=df, marker='o')
    plt.title(f"Monthly Expenses for {year}", fontsize=16)
    plt.xlabel("Month", fontsize=12)
    plt.ylabel("Total Expense ($)", fontsize=12)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png')
    img_buf.seek(0)
    plt.close()
    
    return StreamingResponse(img_buf, media_type="image/png")

@app.get("/charts/yearly_category_line/{year}")
def yearly_category_line_chart(year: int, db: Session = Depends(get_db)):
    expenses = db.query(
        ExpenseDB.category,
        func.extract('month', ExpenseDB.date).label('month'),
        func.sum(ExpenseDB.amount).label('total')
    ).filter(
        func.extract('year', ExpenseDB.date) == year
    ).group_by(
        ExpenseDB.category,
        func.extract('month', ExpenseDB.date)
    ).order_by('category', 'month').all()
    
    categories = list(set([e.category for e in expenses]))
    months = list(range(1, 13))
    
    plt.figure(figsize=(12, 6))
    for category in categories:
        category_data = [next((e.total for e in expenses if e.category == category and e.month == month), 0) for month in months]
        plt.plot(months, category_data, marker='o', label=category)
    
    plt.title(f"Monthly Expenses by Category for {year}")
    plt.xlabel("Month")
    plt.ylabel("Total Expense ($)")
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.xticks(months, [calendar.month_abbr[m] for m in months])
    plt.grid(True)
    plt.tight_layout()
    
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png')
    img_buf.seek(0)
    plt.close()
    
    return StreamingResponse(img_buf, media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)