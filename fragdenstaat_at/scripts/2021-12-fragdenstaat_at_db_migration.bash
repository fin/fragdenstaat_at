#echo "DROP DATABASE fragdenstaat;" | psql -U postgres -h localhost -p 5432 postgres

#psql -U postgres -h localhost -p 5432 postgres < pg_backup.sql


python manage.py migrate



# enable migrations - email now case insensitive, reassign to lowest user id for same case insensitive email.

echo "select email_ci, min(id) as minid, count(id) as nid from account_user group by email_ci having count(*)>1 and email_ci is not null" | python manage.py dbshell
echo "select au.id id_before, info.minid id_after from account_user au left join (select email_ci, min(id) as minid, count(id) as nid from account_user group by email_ci having count(*)>1 and email_ci is not null) info on au.email_ci=info.email_ci where info.minid is not null" | python manage.py dbshell

echo "update foirequest_foirequest  set user_id=id_before_after.id_after from (
    select au.id id_before, info.minid id_after from account_user au left join (select email_ci, min(id) as minid, count(id) as nid from account_user group by email_ci having count(*)>1 and email_ci is not null) info on au.email_ci=info.email_ci where info.minid is not null
    ) id_before_after where foirequest_foirequest.user_id=id_before_after.id_before and id_after is not null
    " | python manage.py dbshell

echo "update foirequest_foimessage  set sender_user_id=id_before_after.id_after from (
    select au.id id_before, info.minid id_after from account_user au left join (select email_ci, min(id) as minid, count(id) as nid from account_user group by email_ci having count(*)>1 and email_ci is not null) info on au.email_ci=info.email_ci where info.minid is not null
    ) id_before_after where foirequest_foimessage.sender_user_id=id_before_after.id_before and id_after is not null
    " | python manage.py dbshell

echo "update foirequest_foievent  set user_id=id_before_after.id_after from (
    select au.id id_before, info.minid id_after from account_user au left join (select email_ci, min(id) as minid, count(id) as nid from account_user group by email_ci having count(*)>1 and email_ci is not null) info on au.email_ci=info.email_ci where info.minid is not null
    ) id_before_after where foirequest_foievent.user_id=id_before_after.id_before and id_after is not null
    " | python manage.py dbshell

echo "select au.id id_before from account_user au left join (select email_ci, min(id) as minid, count(id) as nid from account_user group by email_ci having count(*)>1 and email_ci is not null) info on au.email_ci=info.email_ci where info.minid is not null and au.id!=info.minid" | python manage.py dbshell

echo "delete from  account_user where id in (
    select au.id id_before from account_user au left join (select email_ci, min(id) as minid, count(id) as nid from account_user group by email_ci having count(*)>1 and email_ci is not null) info on au.email_ci=info.email_ci where info.minid is not null and au.id!=info.minid
)" | python manage.py dbshell


python manage.py migrate

python manage.py migrate filer 0011_auto_20190418_0137 --fake
python manage.py migrate




#### EVENTUELL HIER INFOS AUS django_comments tabelle wiederherstellen?

# alle user ohne email und request -> raus
echo "delete from account_user where id in (select id from account_user au left join (select user_id, count(*) request_count from foirequest_foirequest group by user_id) rc on rc.user_id=au.id where email is null and request_count is null)" | python manage.py dbshell

echo "select email, min(id), count(id) from account_user group by email having count(*)>1 and email is null" | python manage.py dbshell

echo "delete from foirequestfollower_foirequestfollower where user_id in (select id from account_user au left join (select user_id, count(*) request_count from foirequest_foirequest group by user_id) rc on rc.user_id=au.id where email is null and request_count is null)" | python manage.py dbshell
echo "select username, first_name, last_name from account_user where email is null" | python manage.py dbshell

echo "update account_user as au set first_name=new_first_name, last_name=new_second_name, email=new_email from (select distinct sender_user_id, regexp_replace(sender_email, '([^.]*)\.([^.]*)\..*$', '\1') as new_first_name, regexp_replace(sender_email, '([^.]*)\.([^.]*)\..*$', '\2') as new_second_name, regexp_replace(sender_email, '([^.]*)\.([^.]*)\..*$', '\1.\2_lost_email@fds.example.com') as new_email from foirequest_foimessage left join account_user on foirequest_foimessage.sender_user_id=account_user.id where account_user.email is null and sender_user_id is not null) new_values where au.email is null and au.id=new_values.sender_user_id;" | python manage.py dbshell

# echo "select user_id, count(*) request_count from foirequest_foirequest group by user_id" | python manage.py dbshell
# echo "select user_id, count(*) comment_count from django_comments group by user_id" | python manage.py dbshell


echo "delete from account_user au using (select user_id, count(*) request_count from foirequest_foirequest group by user_id) rc where rc.user_id=au.id and email is null and request_count is null" | python manage.py dbshell


echo "select au.id, rc.request_count from account_user au left join (select user_id, count(*) request_count, min() from foirequest_foirequest group by user_id) rc on rc.user_id=au.id where email is null and rc.request_count=0" | python manage.py dbshell


# echo "delete from foirequest_foievent where user_id in (select id from account_user where email_ci is null)" | python manage.py dbshell
# echo "delete from foirequest_deliverystatus where message_id in (select id from foirequest_foimessage where sender_user_id in (select id from account_user where email_ci is null))" | python manage.py dbshell
# echo "delete from foirequest_foievent where request_id in (select id from foirequest_foirequest where user_id in (select id from account_user where email_ci is null))" | python manage.py dbshell
# echo "delete from foirequest_publicbodysuggestion where request_id in (select id from foirequest_foirequest where user_id in (select id from account_user where email_ci is null))" | python manage.py dbshell
# echo "delete from foirequest_foimessage where sender_user_id in (select id from account_user where email_ci is null)" | python manage.py dbshell
# echo "delete from foirequest_foiattachment where belongs_to_id in (select id from foirequest_foimessage where request_id in (select id from foirequest_foirequest where user_id in (select id from account_user where email_ci is null)))" | python manage.py dbshell
# echo "delete from foirequest_foimessage where request_id in (select id from foirequest_foirequest where user_id in (select id from account_user where email_ci is null))" | python manage.py dbshell
# echo "delete from foirequest_deferredmessage where request_id in (select id from foirequest_foirequest where user_id in (select id from account_user where email_ci is null))" | python manage.py dbshell
# echo "delete from foirequest_foirequest where user_id in (select id from account_user where email_ci is null)" | python manage.py dbshell
# echo "delete from account_user where email_ci is null" | python manage.py dbshell


# python manage.py migrate --fake-initial publicbody 0009
# python manage.py migrate --fake publicbody 0010


# python manage.py migrate --fake-initial foirequest 0001
# python manage.py migrate --fake foirequest 0002
# python manage.py migrate foirequest 0030

# python manage.py migrate --fake-initial


# # sqldiff
# # - account: account_user_groups, account_user_user_permissions
# # - publicbody: classifications
# # - foirequestfollower: Index

# python manage.py sqldiff -a | python manage.py dbshell

# # python manage.py loaddata fragdenstaat_at/test.json
