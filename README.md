# BPOD Mage Python Code 

#### 这是在mage上运行的python代码
    提供了本地运行的方法

####

## 路径的说明
    1. config
        本地运行的配置文件

    2. files
        本地运行的Load对象文件
        需要按照地区命名子文件路径 例如 /CN /MY 

    3. mage
        mage代码的备份文件

## 如何运行


python -m api.main


## 代码检查
pylint --output=pylint_results.txt 
pylint -r . -ll

bandit --output=bandit_results.txt 
bandit -r . -ll


### 需要启动的类方法名

### 数据文件load

```
kwarg_logger = kwargs.get('logger')
file_list =  kwargs['files']
region =  kwargs['region']
action_user = kwargs['action_user']

# file_list =  "MY MBB,MY M2U".split(",")
# region =  "MY"
# action_user = "appuser"
kwarg_logger.info(f'file check action block .region:{region}. file_list: {file_list}. user:{action_user}')
loac_ctrl = LoadControl(kwarg_logger)

checker_flag = "yes"
for file_pre in file_list:
    print(file_pre)
    ret = loac_ctrl.check_file_can_load(file_pre,region)
    if not ret:
        checker_flag = "no"
        break

kwarg_logger.info(" file check return flg : " + checker_flag)
return checker_flag



```

循环load地区所有文件
```
load_action = LoadAction('Loading Action','',region,kwarg_logger)
if checker_flag=="yes":
    for file_pre in file_list:
        kwarg_logger.info(f'run action load file: {file_pre}')
        load_action.read_pfile_to_table(region,file_pre,action_user)
        kwarg_logger.info(f'finished load action. file {file_pre}')

```

入账 POST

```
region =  kwargs['region']
action_user = kwargs['action_user']
kwarg_logger.info(f'Post match Start Block  . region:[{region}]')
post_action = PostAction('Post Action',kwarg_logger)
post_action.excute_region_posting(region,action_user)
```

Load then post

```
load_action = LoadAction(region,'',region,kwarg_logger)
bank_data = load_action.read_region_all_file(action_user=action_user)

kwarg_logger.info(f'IFP ALL LoadPost load done. region:{region}.user:{action_user}')
# If there has bank data ,do the post match. 
if bank_data > 0:
    if region =="IN":
        action = PostActionIndia('Common post action', kwarg_logger)
    else:
        action = PostAction('Common post action', kwarg_logger)

    action.excute_region_posting(region,action_user=action_user)

    kwarg_logger.info(f'IFP ALL LoadPost posting done. region:{region}.user:{action_user}')
else:
    kwarg_logger.info(f'IFP ALL LoadPost No bank data postmatch skiped. region:{region}.user:{action_user}')
```

load aging then alocate
```
eact = ExecuteAction(kwarg_logger)
eact.exec_load_aging_allocate(region,prefix,action_user)
```

入账结果数据文件生成

```
    post_action = OutputFileAction('Post action', kwarg_logger)

    post_action.output_post_data(region,action_user)
```

销账结果数据文件生成
```
    post_action = OutputFileAction('Post action', kwarg_logger)

    post_action.output_alloc_data(region,action_user)
```

删除文件
```
kwarg_logger = kwargs.get('logger')
regions = kwargs['regions']
days = kwargs['days']
action_user = kwargs['action_user']

kwarg_logger.debug(f"Delete bucket files regions:{regions}. days:{days}")
file_util = FileUtil(logger=kwarg_logger)
for region in regions.split(','):
    kwarg_logger.debug(f"Delete region: {region}")
    file_util.del_cos_files_before_days(region,days)
kwarg_logger.info(f"Delete bucket files region: {region} finished.")
```