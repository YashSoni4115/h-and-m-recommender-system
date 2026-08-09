-- Add 'dislike' to interactions.type. Postgres doesn't let you alter a check
-- constraint in place, so drop & recreate.
alter table interactions drop constraint if exists interactions_type_check;
alter table interactions
  add constraint interactions_type_check
  check (type in ('like', 'cart', 'dislike'));
