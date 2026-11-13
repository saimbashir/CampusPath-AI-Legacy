"""Run the actual frozen migrations and launcher in a clean copied source tree."""
import os,sys,subprocess,sqlite3,shutil
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture()
def release(tmp_path):
    source=tmp_path/'release'
    shutil.copytree(ROOT,source,ignore=shutil.ignore_patterns('.venv','.env','*.db','*.db-*','__pycache__','.pytest_cache','node_modules','backups','fixtures.json'))
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(source/'campuspath.db'),'DEMO_MODE':'true'}
    def run(*args):
        result=subprocess.run([sys.executable,*args],cwd=source,env=env,text=True,capture_output=True,timeout=40)
        assert result.returncode==0,result.stdout+'\n'+result.stderr
        return result
    return source,env,run

def test_clean_launcher_check_idempotent_and_backup(release):
    source,env,run=release
    first=run('run.py','--check');assert 'Schema: 0003' in first.stdout
    with sqlite3.connect(source/'campuspath.db') as db:
        count=db.execute('SELECT count(*) FROM users').fetchone()[0];db.execute("UPDATE users SET name='Saved edited name' WHERE id=2");db.commit()
    run('run.py','--check','--backup')
    with sqlite3.connect(source/'campuspath.db') as db:
        assert db.execute('SELECT count(*) FROM users').fetchone()[0]==count
        assert db.execute('SELECT name FROM users WHERE id=2').fetchone()[0]=='Saved edited name'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    backups=list((source/'backups').glob('*.db'));assert len(backups)==1
    with sqlite3.connect(backups[0]) as db:assert db.execute('SELECT name FROM users WHERE id=2').fetchone()[0]=='Saved edited name'
    assert (source/'.env').exists()

def test_v1_upgrade_preserves_records_and_downgrade_roundtrip(release):
    source,env,run=release
    run('-m','alembic','upgrade','0001')
    with sqlite3.connect(source/'campuspath.db') as db:
        db.execute("INSERT INTO users (id,email,name,university_id,password,role) VALUES (1,'existing@example.test','Existing Person','EX-1','not-a-real-hash','student')");db.commit()
    result=run('run.py','--check');assert 'sample data was not inserted' in result.stdout
    with sqlite3.connect(source/'campuspath.db') as db:
        assert db.execute('SELECT name,active FROM users').fetchall()==[('Existing Person',1)]
        assert db.execute('SELECT count(*) FROM study_plans').fetchone()[0]==0
    assert len(list((source/'backups').glob('*.db')))==1
    run('-m','alembic','downgrade','0001');run('-m','alembic','upgrade','head')
    with sqlite3.connect(source/'campuspath.db') as db:
        assert db.execute('SELECT name,active FROM users').fetchall()==[('Existing Person',1)]
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
