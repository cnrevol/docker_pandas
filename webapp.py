"""
提供webapi访问
"""

import time

from flask import Flask, jsonify, request

from load_common import LoadAction
from utils.logger import BpodLogger
from post_common import PostAction
from post_india import PostActionIndia

from output_common import OutputFileAction
from allocate_common import AllocateAction
from allocate_cn import ChinaAllocateAction
from allocate_run import AllocateFactory

app = Flask(__name__)

log_instance = BpodLogger()

alloc_factory = AllocateFactory()
alloc_factory.register("AllocateAction", AllocateAction)
alloc_factory.register("ChinaAllocateAction", ChinaAllocateAction)
# here could dynamic init action.
alloc_action_cn = alloc_factory.allocate_get(
    "ChinaAllocateAction", "ChinaAction", log_instance
)
alloc_action = alloc_factory.allocate_get(
    "AllocateAction", "commonAction", log_instance
)

post_action = PostAction("Common post action", log_instance)
inpost_action = PostActionIndia("India post action", log_instance)

load_action = LoadAction("Common load ", "", "", log_instance)

outfile_action = OutputFileAction("Post action", log_instance)


@app.route("/")
def index():
    """
    index page
    """
    return "BPOD IFP PROJECT!"


@app.route("/api/loadfile", methods=["GET"])
def load_files():
    """
    加载数据文件
    """
    log_instance.debug("Load file get api kicked.")
    region = request.args.get("region")
    action_user = request.args.get("action_user")
    file_list = request.args.get("files")

    duration = execute_action_and_measure_time(
        region, action_user, excute_load_action, file_list
    )

    return jsonify({"message": f"File load finished!  cost time: {duration}"})



@app.route("/api/agingpost", methods=["GET"])
def aging_post_get():
    """
    aging data match
    """
    log_instance.debug("aging match get api kicked.")

    region = request.args.get("region")
    action_user = request.args.get("action_user")

    duration = execute_action_and_measure_time(region, action_user, excute_post_action)

    return jsonify({"message": f"Post Match finished!  cost time: {duration}"})

@app.route("/api/allocate", methods=["GET"])
def allocate():
    """
    aging data allocate
    """

    log_instance.debug("allocate get api kicked.")
    region = request.args.get("region")
    action_user = request.args.get("action_user")

    duration = execute_action_and_measure_time(
        region, action_user, excute_allocate_action
    )

    return jsonify({"message": f"Allocate finished!  cost time: {duration}"})

@app.route("/api/postfile", methods=["GET"])
def postfile():
    """
    post file output
    """

    log_instance.debug("post file output get api kicked.")
    region = request.args.get("region")
    action_user = request.args.get("action_user")

    duration = execute_action_and_measure_time(
        region, action_user, excute_output_file_action
    )

    return jsonify({"message": f"post file output finished!  cost time: {duration}"})

@app.route("/api/allocatefile", methods=["GET"])
def allocatefile():
    """
    allocate file output
    """

    log_instance.debug("allocate file output get api kicked.")
    region = request.args.get("region")
    action_user = request.args.get("action_user")

    duration = execute_action_and_measure_time(
        region, action_user, excute_allocate_file_action
    )

    return jsonify({"message": f"allocate file output finished!  cost time: {duration}"})


@app.route("/api/loadfile", methods=["POST"])
def load_files_post():
    """
    加载数据文件
    """

    log_instance.debug("Load file post api kicked.")
    region, action_user, file_list = get_json_param2()

    duration = execute_action_and_measure_time(
        region, action_user, excute_load_action, file_list
    )

    return jsonify({"message": f"File load finished!  cost time: {duration}"})


@app.route("/api/agingpost", methods=["POST"])
def aging_post():
    """
    aging data match
    """

    log_instance.debug("aging match post api kicked.")

    region, action_user = get_json_param()

    duration = execute_action_and_measure_time(region, action_user, excute_post_action)

    return jsonify({"message": f"Post Match finished!  cost time: {duration}"})

@app.route("/api/allocate", methods=["POST"])
def allocate_post():
    """
    aging data allocate
    """
    log_instance.debug("allocate post api kicked.")

    region, action_user = get_json_param()

    duration = execute_action_and_measure_time(
        region, action_user, excute_allocate_action
    )

    return jsonify({"message": f"Allocate finished!  cost time: {duration}"})

@app.route("/api/postfile", methods=["POST"])
def postfilepost():
    """
    post file output
    """

    log_instance.debug("post file output post api kicked.")
    region, action_user = get_json_param()

    duration = execute_action_and_measure_time(
        region, action_user, excute_output_file_action
    )

    return jsonify({"message": f"post file output finished!  cost time: {duration}"})


@app.route("/api/allocatefile", methods=["POST"])
def allocatefilepost():
    """
    allocate file output
    """
    log_instance.debug("allocate file output get api kicked.")
    region, action_user = get_json_param()

    duration = execute_action_and_measure_time(
        region, action_user, excute_allocate_file_action
    )

    return jsonify({"message": f"allocate file output finished!  cost time: {duration}"})

def excute_load_action(region, action_user, file_list):
    """
    执行load方法
    """
    for file_pre in file_list:
        log_instance.info(f"run action load file: {file_pre}")
        load_action.read_pfile_to_table(region, file_pre, action_user)
        log_instance.info(f"finished load action. file {file_pre}")

def excute_post_action(region, action_user):
    """
    执行Action方法
    """
    if region == "IN":
        inpost_action.excute_region_posting(region, action_user)
    else:
        post_action.excute_region_posting(region, action_user)

def excute_allocate_action(region, action_user):
    """
    执行Allocate方法
    """
    if region == "CN":
        alloc_action_cn.excute_region_allocate(region, action_user)
    else:
        alloc_action.excute_region_allocate(region, action_user)

def excute_output_file_action(region, action_user):
    """
    执行 Post Output file方法
    """
    outfile_action.output_post_data(region, action_user)

def excute_allocate_file_action(region, action_user):
    """
    执行 Allocate Output file方法
    """
    outfile_action.output_alloc_data(region, action_user)

def get_json_param():
    """
    取得post body参数
    """
    data = request.json
    variables = data.get("variables", {})
    region = variables.get("region")
    action_user = variables.get("action_user")
    return region,action_user

def get_json_param2():
    """
    取得post body参数
    """
    data = request.json
    variables = data.get("variables", {})
    region = variables.get("region")
    action_user = variables.get("action_user")
    file_list = variables.get("files")
    return region,action_user,file_list

def execute_action_and_measure_time(
    region, action_user, action_function, *args, **kwargs
):
    """
    动态调用
    """
    # 获取开始时间
    start_time = time.time()

    # 执行动作，并传递额外的参数
    action_function(region, action_user, *args, **kwargs)

    # 获取结束时间
    end_time = time.time()

    # 计算经过的时长
    duration = end_time - start_time

    return duration


if __name__ == "__main__":
    # app.run(host='0.0.0.0',)
    app.run(port=8000, debug=True)
