from uuid import uuid4
from psycopg.types.json import Jsonb
from platform_app import store


def test_progress_survives_database_reload_and_server_blocks_skipping(client, roster):
    aid, tid = uuid4(), uuid4()
    objectives=['Explain the effect of new feedback.', 'Justify a change based on that feedback.']
    step={'title':'Respond to feedback','goal':'Explain how feedback affects the next work.', 'objectives':objectives}
    config={'learning_steps':[step,{**step,'title':'Discuss priorities'}], 'minimum_step_questions':10}
    progress={'objectives':objectives,'met':{'0':{'quote':'Feedback reveals that mobile signup fails.', 'reason':'Identifies new evidence.'}}}
    state={'socratic':{'phase':'teaching','learning_step_index':0,'step_started_at_message_count':1,'objective_progress':{'0':progress}}}
    messages=[{'role':'assistant','content':'What should the team inspect?'}, {'role':'user','content':'Feedback reveals that mobile signup fails.'}]
    with store.connection() as conn:
        conn.execute('''INSERT INTO assignments_platform (id,course_id,creator_id,tool,title,status,audience,config,snapshot)
            VALUES (%s,%s,%s,'socratic','Mission progress','published','course',%s,%s)''',
            (aid,roster['course'],roster['prof'],Jsonb(config),Jsonb({'config':config,'chunks':[]})))
        conn.execute('INSERT INTO assignment_recipients_platform (assignment_id,student_id) VALUES (%s,%s)',(aid,roster['student']))
        conn.execute('''INSERT INTO assignment_attempts_platform (id,assignment_id,student_id,engine_state,messages)
            VALUES (%s,%s,%s,%s,%s)''',(tid,aid,roster['student'],Jsonb(state),Jsonb(messages)))
    headers=roster['headers']['student']
    detail=client.get(f'/api/platform/assignments/{aid}',headers=headers)
    assert detail.status_code==200
    assert detail.json()['student_config']['learning_steps'][0]['objectives']==objectives
    attempt=client.get(f'/api/platform/assignments/{aid}/attempt',headers=headers)
    assert attempt.status_code==200
    assert attempt.json()['engine_state']['socratic']['objective_progress']['0']==progress
    denied=client.post(f'/api/platform/assignments/{aid}/next-step',headers=headers)
    assert denied.status_code==409 and 'remaining mission objectives' in denied.text
    with store.connection() as conn:
        saved=conn.execute('SELECT * FROM assignment_attempts_platform WHERE id=%s',(tid,)).fetchone()
        saved['engine_state']['socratic']['objective_progress']['0']['met']['1']={
            'quote':'Fix signup before event listings because registration is the goal.', 'reason':'Justifies the change.'}
        store.save_attempt(conn,saved)
    advanced=client.post(f'/api/platform/assignments/{aid}/next-step',headers=headers)
    assert advanced.status_code==200
    assert advanced.json()['engine_state']['socratic']['learning_step_index']==1
    assert len(advanced.json()['engine_state']['socratic']['objective_progress']['0']['met'])==2
    with store.connection() as conn:
        reread=conn.execute('SELECT engine_state FROM assignment_attempts_platform WHERE id=%s',(tid,)).fetchone()
        assert len(reread['engine_state']['socratic']['objective_progress']['0']['met'])==2
