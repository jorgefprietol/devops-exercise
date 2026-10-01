"""Genera CloudFormation para una evaluacion temporal de dos nodos Kubernetes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def template():
    ref = lambda name: {'Ref': name}
    sub = lambda value: {'Fn::Sub': value}
    attr = lambda name, key: {'Fn::GetAtt': [name, key]}
    resources = {}
    def add(name, kind, **props):
        resources[name] = {'Type': 'AWS::' + kind, 'Properties': props}
    def policy(actions, resource, **extra):
        return {'Effect': 'Allow', 'Action': actions, 'Resource': resource, **extra}
    def document(statements):
        return {'Version': '2012-10-17', 'Statement': statements}
    def trust(service):
        return document([{'Effect': 'Allow', 'Principal': {'Service': service}, 'Action': 'sts:AssumeRole'}])
    tags = [{'Key': 'Project', 'Value': 'devops-evaluacion'}]
    add('Vpc', 'EC2::VPC', CidrBlock='10.80.0.0/16', EnableDnsSupport=True, EnableDnsHostnames=True, Tags=tags)
    add('Internet', 'EC2::InternetGateway', Tags=tags)
    add('AttachInternet', 'EC2::VPCGatewayAttachment', VpcId=ref('Vpc'), InternetGatewayId=ref('Internet'))
    add('Routes', 'EC2::RouteTable', VpcId=ref('Vpc'), Tags=tags)
    add('InternetRoute', 'EC2::Route', RouteTableId=ref('Routes'), DestinationCidrBlock='0.0.0.0/0', GatewayId=ref('Internet'))
    resources['InternetRoute']['DependsOn'] = 'AttachInternet'
    for index in (0, 1):
        name = 'Subnet' + str(index)
        add(name, 'EC2::Subnet', VpcId=ref('Vpc'), CidrBlock=f'10.80.{index}.0/24',
            AvailabilityZone={'Fn::Select': [index, {'Fn::GetAZs': ''}]}, MapPublicIpOnLaunch=True, Tags=tags)
        add(name + 'Route', 'EC2::SubnetRouteTableAssociation', SubnetId=ref(name), RouteTableId=ref('Routes'))
    add('NodesSecurity', 'EC2::SecurityGroup', GroupDescription='HTTPS publico y red privada Kubernetes; sin SSH',
        VpcId=ref('Vpc'), SecurityGroupIngress=[{'IpProtocol': 'tcp', 'FromPort': p, 'ToPort': p, 'CidrIp': '0.0.0.0/0'} for p in (80, 443)], Tags=tags)
    for name, proto, port in [('Api', 'tcp', 6443), ('Kubelet', 'tcp', 10250), ('Overlay', 'udp', 8472)]:
        add('Private' + name, 'EC2::SecurityGroupIngress', GroupId=ref('NodesSecurity'),
            SourceSecurityGroupId=ref('NodesSecurity'), IpProtocol=proto, FromPort=port, ToPort=port)
    token_arn = sub('arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/${AWS::StackName}/cluster-token')
    for role in ('Server', 'Worker'):
        add(role + 'Role', 'IAM::Role', AssumeRolePolicyDocument=trust('ec2.amazonaws.com'),
            ManagedPolicyArns=['arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore'],
            Policies=[{'PolicyName': 'TokenDeUnion', 'PolicyDocument': document([
                policy(['ssm:GetParameter'] + (['ssm:PutParameter'] if role == 'Server' else []), token_arn)])}])
        add(role + 'Profile', 'IAM::InstanceProfile', Roles=[ref(role + 'Role')])
        bootstrap = (ROOT / 'infra/cloud/aws/bootstrap.sh').read_text()
        bootstrap = bootstrap.replace('__REGION__', '${AWS::Region}').replace('__TOKEN_PARAMETER__', '/${AWS::StackName}/cluster-token')
        bootstrap = bootstrap.replace('__NODE_ROLE__', role.lower() if role == 'Server' else 'agent')
        bootstrap = bootstrap.replace('__SERVER_IP__', '${Server.PrivateIp}' if role == 'Worker' else '')
        add(role, 'EC2::Instance', ImageId=ref('UbuntuAmi'), InstanceType='t3.medium',
            CreditSpecification={'CPUCredits': 'standard'}, IamInstanceProfile=ref(role + 'Profile'),
            SubnetId=ref('Subnet0' if role == 'Server' else 'Subnet1'), SecurityGroupIds=[ref('NodesSecurity')],
            MetadataOptions={'HttpTokens': 'required', 'HttpPutResponseHopLimit': 1},
            InstanceInitiatedShutdownBehavior='terminate',
            BlockDeviceMappings=[{'DeviceName': '/dev/sda1', 'Ebs': {'VolumeSize': 30, 'VolumeType': 'gp3', 'Encrypted': True, 'DeleteOnTermination': True}}],
            UserData={'Fn::Base64': sub(bootstrap)}, Tags=tags + [{'Key': 'Name', 'Value': 'devops-' + role.lower()}])
        resources[role]['DependsOn'] = ['InternetRoute', 'Subnet0Route', 'Subnet1Route']
    instance_arns = [sub('arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:instance/${' + name + '}') for name in ('Server', 'Worker')]
    add('ExpiryRole', 'IAM::Role', AssumeRolePolicyDocument=trust('scheduler.amazonaws.com'),
        Policies=[{'PolicyName': 'EliminarDosNodos', 'PolicyDocument': document([policy('ec2:TerminateInstances', instance_arns)])}])
    add('Expiry', 'Scheduler::Schedule', ScheduleExpression=sub('at(${ExpiresUtc})'), ScheduleExpressionTimezone='UTC',
        FlexibleTimeWindow={'Mode': 'OFF'}, State='ENABLED', ActionAfterCompletion='DELETE',
        Target={'Arn': 'arn:aws:scheduler:::aws-sdk:ec2:terminateInstances', 'RoleArn': attr('ExpiryRole', 'Arn'),
                'Input': sub('{"InstanceIds":["${Server}","${Worker}"]}'),
                'RetryPolicy': {'MaximumEventAgeInSeconds': 3600, 'MaximumRetryAttempts': 10}})
    add('Budget', 'Budgets::Budget', Budget={'BudgetName': sub('${AWS::StackName}-10-usd'), 'BudgetType': 'COST',
        'TimeUnit': 'MONTHLY', 'BudgetLimit': {'Amount': 10, 'Unit': 'USD'}})
    add('GithubOidc', 'IAM::OIDCProvider', Url='https://token.actions.githubusercontent.com', ClientIdList=['sts.amazonaws.com'])
    add('DeployDocument', 'SSM::Document', DocumentType='Command', Content={
        'schemaVersion': '2.2', 'description': 'Desplegar una revision e imagen verificadas del repositorio',
        'parameters': {'Revision': {'type': 'String', 'allowedPattern': '^[a-f0-9]{40}$', 'interpolationType': 'ENV_VAR'},
                       'Image': {'type': 'String', 'allowedPattern': '^ghcr.io/jorgefprietol/devops-exercise@sha256:[a-f0-9]{64}$', 'interpolationType': 'ENV_VAR'},
                       'Environment': {'type': 'String', 'allowedValues': ['production', 'staging', 'development'], 'interpolationType': 'ENV_VAR'}},
        'mainSteps': [{'action': 'aws:runShellScript', 'name': 'Desplegar', 'inputs': {'timeoutSeconds': '1200', 'runCommand': [
            'set -eu', 'umask 077', 'test -f /opt/devops/bootstrap-completo',
            'exec 9>/opt/devops/despliegue.lock; flock -w 1200 9',
            'DEST="/opt/devops/releases/$SSM_Revision"; mkdir -p "$DEST"',
            'curl --fail --location --retry 3 "https://api.github.com/repos/jorgefprietol/devops-exercise/tarball/$SSM_Revision" -o /opt/devops/release.tar.gz',
            'tar -xzf /opt/devops/release.tar.gz --strip-components=1 -C "$DEST"',
            'python3 "$DEST/scripts/aws_apply.py" --environment "$SSM_Environment" --image "$SSM_Image"']}}]})
    add('GithubRole', 'IAM::Role', AssumeRolePolicyDocument=document([{'Effect': 'Allow',
        'Principal': {'Federated': ref('GithubOidc')}, 'Action': 'sts:AssumeRoleWithWebIdentity',
        'Condition': {'StringEquals': {'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com'},
                      'StringLike': {'token.actions.githubusercontent.com:sub': [
                          'repo:jorgefprietol/devops-exercise:ref:refs/heads/master',
                          'repo:jorgefprietol/devops-exercise:ref:refs/heads/develop',
                          'repo:jorgefprietol/devops-exercise:ref:refs/tags/v*']}}}]),
        Policies=[{'PolicyName': 'DesplegarSoloEnServidor', 'PolicyDocument': document([
            policy('ssm:SendCommand', [instance_arns[0], sub('arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:document/${DeployDocument}')]),
            policy('ssm:GetCommandInvocation', '*')])}])
    return {'AWSTemplateFormatVersion': '2010-09-09', 'Description': 'Evaluacion temporal DevOps: dos nodos, HTTPS y cierre automatico',
        'Parameters': {'UbuntuAmi': {'Type': 'AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>',
                                    'Default': '/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id'},
                       'ExpiresUtc': {'Type': 'String', 'AllowedPattern': r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$',
                                      'Description': 'Fecha UTC de eliminacion de los dos servidores; maximo 72 horas para esta evaluacion'}},
        'Resources': resources, 'Outputs': {'ServerId': {'Value': ref('Server')}, 'WorkerId': {'Value': ref('Worker')},
            'PublicIp': {'Value': attr('Server', 'PublicIp')}, 'RoleArn': {'Value': attr('GithubRole', 'Arn')},
            'DeployDocument': {'Value': ref('DeployDocument')}, 'ExpirySchedule': {'Value': ref('Expiry')}}}


if __name__ == '__main__':
    print(json.dumps(template(), indent=2))
