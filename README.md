# whitepaper_rag

激活venv环境
source backend/venv/bin/activate
安装依赖
pip install -r backend/requirements.txt
启动项目
python -m uvicorn backend.app.main:app --reload    

运行测试
pytest