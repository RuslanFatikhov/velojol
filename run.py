from app import create_app, db
import os

# Создаем приложение
app = create_app()

@app.shell_context_processor
def make_shell_context():
    """Контекст для flask shell"""
    return {'db': db}

if __name__ == '__main__':
    # Создаем таблицы если их нет
    with app.app_context():
        db.create_all()
    
    # Запускаем приложение
    app.run(debug=True, host='127.0.0.1', port=5000)
