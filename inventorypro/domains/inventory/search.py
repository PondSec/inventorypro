"""Bounded cross-module search with the same read boundaries as each module."""
from urllib.parse import urlencode
from .service import list_inventory


def search_workspace(db,query,*,can,access,ticket_visible):
    query=str(query or '').strip()[:240]
    if len(query)<2:return []
    escaped=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    like='%'+escaped+'%';groups=[]
    def add(label,items,more=''):
        if items:groups.append({'label':label,'items':items,'more':more})
    inventory=list_inventory(db,{'q':query,'per_page':10},devices_allowed=can('devices.view') or can('devices.manage'),assets_allowed=can('assets.view') or can('assets.manage'))
    add('Inventar',[{'title':row['name'],'description':' · '.join(str(value) for value in [row['serial_number'],row['category'],row['location']] if value),
        'href':f"/inventory/{'devices' if row['kind']=='device' else 'assets'}/{row['id']}",'icon':row['icon']} for row in inventory['rows']],'/inventory?'+urlencode({'q':query}))
    if can('tickets.view_all') or can('tickets.view_own'):
        db.create_function('inventory_casefold',1,lambda value:str(value or '').strip().casefold(),deterministic=True)
        sql="SELECT * FROM tickets WHERE (title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' OR CAST(id AS TEXT)=?)"
        args=[like,like,query.lstrip('#')]
        if not (access['is_superuser'] or 'tickets.view_all' in access['permissions']):
            sql+=" AND (created_by_user_id=? OR (created_by_user_id IS NULL AND (inventory_casefold(created_by)=? OR inventory_casefold(requester_name)=?)))"
            args.extend([access['user']['id'],access['user']['username'].strip().casefold(),access['user']['username'].strip().casefold()])
        rows=db.execute(sql+' ORDER BY updated_at DESC,id DESC LIMIT 10',args)
        add('Tickets',[{'title':f"#{row['id']} · {row['title']}",'description':row['status'],'href':f"/tickets/{row['id']}",'icon':'inbox'} for row in rows if ticket_visible(dict(row),access)],'/tickets?'+urlencode({'queue':'all-open','search':query}))
    if can('knowledge.view') or can('knowledge.manage'):
        rows=db.execute("SELECT id,title,summary FROM knowledge_entries WHERE title LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\' ORDER BY updated_at DESC,id DESC LIMIT 10",(like,like,like))
        add('Wissensbasis',[{'title':row['title'],'description':row['summary'] or '', 'href':'/knowledge?'+urlencode({'entry_id':row['id']}),'icon':'book-open'} for row in rows])
    if can('roadmap.view') or can('roadmap.manage'):
        rows=db.execute("SELECT id,title,objective,status FROM roadmaps WHERE title LIKE ? ESCAPE '\\' OR objective LIKE ? ESCAPE '\\' ORDER BY updated_at DESC,id DESC LIMIT 10",(like,like))
        add('Roadmap',[{'title':row['title'],'description':row['objective'] or '', 'href':'/roadmap?'+urlencode({'roadmap_id':row['id']}),'icon':'git-merge'} for row in rows])
    return groups
