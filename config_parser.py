from akamaiproperty import AkamaiProperty
import json

criteria_stack = []
condition_json = []
condition_json1 = []

def parseChildCriteriaBehaviors(rule_list,criteria_stack,level=0):
    if len(rule_list) == 0:
        return
    for rule in reversed(rule_list):
        criteria_dict = {}
        criteria_dict['criteria'] = rule['criteria']
        criteria_dict['condition'] = rule['criteriaMustSatisfy']
        criteria_stack.append(criteria_dict)
        parseChildCriteriaBehaviors(rule['children'],criteria_stack,level+1)
        for behavior in rule['behaviors']:
            condition_dict = {}
            condition_dict['behavior'] = behavior
            condition_dict['criteria'] = criteria_stack.copy()
            condition_json.insert(0,condition_dict)
        temp = criteria_stack.pop()

def parseConfig(parseConfig,accountSwitchKey,configName,version):
    myProperty = AkamaiProperty(parseConfig,configName,accountSwitchKey)
    ruleTree = myProperty.getRuleTree(int(version))

    for default_behaviors in ruleTree['rules']['behaviors']:
        criteria_dict = {}
        criteria_dict['criteria'] = []
        criteria_dict['condition'] = 'all'

        condition_dict1 = {}
        condition_dict1['behavior'] = default_behaviors
        condition_dict1['criteria'] = criteria_dict
        condition_json1.append(condition_dict1)

    parseChildCriteriaBehaviors(ruleTree['rules']['children'],criteria_stack)

    condition_jsonfinal = condition_json1 + condition_json
    return condition_jsonfinal
