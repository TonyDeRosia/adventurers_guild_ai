import sqlite3
import pytest
from engine.written_content import WrittenContentService, WrittenContentData


def svc(tmp_path):
    return WrittenContentService(tmp_path/'written.sqlite', world_root='worlds/shattered_realms')


def test_document_versions_sanitization_copy_and_restart(tmp_path):
    s=svc(tmp_path)
    doc=s.create_document('actor_a', title='Note', subject='Subject', body='Line 1\nLine 2')
    v2=s.edit_document('actor_a', doc, body='Updated')
    assert v2 != s.trace_document(doc)['versions'][0]['content_version_id']
    copied=s.copy_document('actor_b', doc)
    assert copied != doc
    with pytest.raises(ValueError):
        s.create_document('actor_a', body='bad\x1b[31m')
    s2=svc(tmp_path)
    assert s2.get_document(doc)['body_text']=='Updated'


def test_mailbox_delivery_read_idempotency_and_isolation(tmp_path):
    s=svc(tmp_path)
    doc=s.compose_mail('sender',[{'type':'actor','id':'one'},{'type':'actor','id':'two'}],'Hello','Body')
    first=s.send_mail('sender', doc)
    second=s.send_mail('sender', doc)
    assert first==second
    mb1=s.get_mailbox('actor','one')['mailbox_id']; mb2=s.get_mailbox('actor','two')['mailbox_id']
    assert len(s.list_mail(mb1))==1 and len(s.list_mail(mb2))==1
    assert s.mark_mail_read('one', first[0]) is True
    assert s.mark_mail_read('one', first[0]) is True
    assert s.list_mail(mb2)[0]['status']=='delivered'
    s.archive_mail('one', first[0]); s.delete_mail('one', first[0]); s.restore_mail('one', first[0])
    assert s.trace_mail(first[0])['delivery']['status']=='delivered'


def test_attachments_claim_once_and_board_threads_moderation(tmp_path):
    s=svc(tmp_path)
    doc=s.compose_mail('sender',[{'type':'actor','id':'one'}],'With item','Body')
    att=s.add_item_attachment('sender', doc, 'item_exact_1')
    delivery=s.send_mail('sender', doc)[0]
    assert s.claim_attachment('one', att, delivery) is True
    assert s.claim_attachment('one', att, delivery) is False
    root=s.post_board_message('actor_a','guildlands_public_board','First','Testing board')
    reply=s.post_board_message('actor_b','guildlands_public_board','Re','Reply',root)
    rows=s.list_board('guildlands_public_board')
    assert [r['document_instance_id'] for r in rows]==[root,reply]
    s.moderate_board_post('mod', root, 'hide', 'reason', new_status='hidden')
    assert s.list_board('guildlands_public_board')[0]['status']=='hidden'


def test_builder_written_collections_validate_pilot_content():
    data=WrittenContentData('worlds/shattered_realms')
    result=data.validate()
    assert result['errors']==[]
    assert {'guildlands_public_board','adventurers_guild_board','town_guard_notice_board'} <= set(data.data['bulletin_board_definitions'])
    assert {'welcome_to_guildlands','guildlands_rules_notice','blacksmiths_note','healers_order_primer','cellar_rat_report'} <= set(data.data['written_document_definitions'])
