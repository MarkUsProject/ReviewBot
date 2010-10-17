import json
from restclient import Resource

DEBUG = True


def msg(msg):
    if DEBUG:
        print msg


class Member(object):
    def __init__(self, member_key, score):
        self.member_key = member_key
        self.score = score

    def add_score(self, score):
        self.score += score


class Group(object):
    def __init__(self, group_name):
        self.name = group_name
        self.members = []

    def add_member(self, member):
        self.members.append(member)

    def pick_reviewer(self):
        return self.members[0]


class GroupManager(object):
    def __init__(self, groups_file):
        self.groups_file = groups_file
        self.groups = []

    def load(self):
        f = open(self.groups_file, 'r', 0)
        groups_info = json.load(f)
        f.close

        for group_name, group_members in groups_info.items():
           group = Group(group_name)
           for member_key, member_data in group_members.items():
               member = Member(member_key, int(member_data['score']))
               group.add_member(member)
           self.groups.append(group)

    def get_groups(self):
        return self.groups

    def save(self):
        out_json = {}
        for group in self.groups:
            out_json[group.name] = {}
            for member in group.members:
                out_json[group.name][member.member_key] = {'score': member.score}
            
        f = open(self.groups_file, 'w', 0)
        json.dump(out_json, f)
        f.close()


class ReviewRequest(object):
    def __init__(self, request):
        self.id = request['id']
        self.requester = request['links']['submitter']['title']

    def get_score(self):
        return 10

    def add_reviewer(self, member):
        pass


class ReviewRequestManager(object):
    def __init__(self, config):
        self.url = config['url']
        self.last_seen_rr = config['last_seen_rr']
        self.conn = Resource(self.url)

    def __str__(self):
        return "URL: %s\nLast Seen Review Request: %s\n" % (self.url, 
            self.last_seen_rr)

    def get_unseen(self):
        unseen = []
        open_reqs = self.get_open_reqs()
        unseen_highest_id = 0
        for request in open_reqs:
           request_id = int(request['id'])
           if request_id > self.last_seen_rr:
               unseen.append(ReviewRequest(request))
           if request_id > unseen_highest_id:
               unseen_highest_id = request_id

        self.last_seen_rr = unseen_highest_id
        return unseen

    def get_open_reqs(self):
        # Query the RB WebAPI, and find all of the open review requests.
        response = self.conn.get("/review-requests", params={'status':'pending'}) 
        response_data = json.loads(response)
        return response_data['review_requests']



class ReviewBot(object):
    def __init__(self, config_file, groups_file):
        self.group_manager = GroupManager(groups_file)
        self.config_file = config_file
        self.config = self.get_config()
        self.rr_manager = ReviewRequestManager(self.config['reviewboard'])

    def get_config(self):
        f = open(self.config_file, 'r', 0)
        config = json.load(f)
        f.close()
        return config

    def save_config(self):
        self.config['reviewboard']['last_seen_rr'] = self.rr_manager.last_seen_rr
        f = open(self.config_file, 'w', 0)
        json.dump(self.config, f)
        f.close()

    def run(self):

        unseen_review_requests = self.rr_manager.get_unseen()

        if not unseen_review_requests:
            # Bail out early
            return 0

        # Load up the groups
        self.group_manager.load()
        groups = self.group_manager.get_groups()

        # Let's see if there are new review requests to look at
        for review_request in unseen_review_requests:
            for group in groups:
                reviewer = group.pick_reviewer()
                review_request.add_reviewer(reviewer)
                reviewer.add_score(review_request.get_score())

            # TODO:  Notification

        # Save everything
        self.group_manager.save()
        self.save_config()

        return 0

if __name__ == "__main__":
    rb = ReviewBot('config.json', 'groups.json')
    rb.run()

