# Copyright (c) 2018 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function
import re
import functools
import warnings
import string

from six.moves import cStringIO
from paddle.fluid.proto import framework_pb2
from paddle.fluid.framework import OpProtoHolder, Variable
from paddle.fluid.layer_helper import LayerHelper

g_filer_attrs = ['op_role', 'op_role_var', 'op_namescope']


def _convert_(name):
    """
    Formatting.

    Args:
       name: The name/alias

    This function takes in a name and converts it to a standard format of
    group1_group2. Where as per the regular expression, group1 can have
    alphabets and numbers and group2 has capital alphabets.

    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def _get_inputs(op_type):
    op_proto = OpProtoHolder.instance().get_op_proto(op_type)
    inputs = dict()
    for ipt in op_proto.inputs:
        inputs[ipt.name] = ipt.comment

    return inputs


def _get_outputs(op_type):
    op_proto = OpProtoHolder.instance().get_op_proto(op_type)
    outputs = {}
    for ipt in op_proto.outputs:
        outputs[ipt.name] = ""

    return outputs


_two_dollar_pattern_ = re.compile(r"\$\$([^\$]+)\$\$")
_single_dollar_pattern_ = re.compile(r"\$([^\$]+)\$")
_two_bang_pattern_ = re.compile(r"!!([^!]+)!!")


def escape_math(text):
    return _two_bang_pattern_.sub(
        r'$$\1$$',
        _single_dollar_pattern_.sub(r':math:`\1`',
                                    _two_dollar_pattern_.sub(r"!!\1!!", text)))


def get_comment(op_type):
    op_proto = OpProtoHolder.instance().get_op_proto(op_type)

    comment_lines = op_proto.comment.split("\n")
    comment = ""
    for line in comment_lines:
        line = line.strip()
        if len(line) != 0:
            comment += escape_math(line)
            comment += " "
        elif len(comment) != 0:
            comment += "\n    "

    return comment


def _get_attrs(op_type):
    op_proto = OpProtoHolder.instance().get_op_proto(op_type)
    return op_proto.attrs


def get_indent_space(indent, space_num=4):
    ret = ""
    for i in range(0, indent * space_num):
        ret += " "

    return ret


def get_input_comments(op_type, indent=2):
    ret = ""
    inputs = _get_inputs(op_type)
    for t in inputs:
        ret += get_indent_space(2) + "%s (Type): %s\n" % (_convert_(t),
                                                          inputs[t])

    for t in _get_attrs(op_type):
        if t.name in g_filer_attrs:
            continue
        ret += get_indent_space(2) + "%s (%s): %s\n" % (
            _convert_(t.name), t.type, _convert_(t.comment))

    return ret


def get_output_comments(op_type, indent=2):
    ret = ""
    for t in _get_outputs(op_type):
        ret += get_indent_space(2) + "output(${%s_type}): ${%s_comment}\n" % (
            _convert_(t), _convert_(t))
    return ret


def get_func_args(op_type):
    ret = ""
    inputs = _get_inputs(op_type)
    for t in inputs:
        ret += "%s," % _convert_(t)

    for t in _get_attrs(op_type):
        if t.name in g_filer_attrs:
            continue

        default = re.findall("\(.+\, default (.+)\(?\)", t.comment)
        if len(default) > 0:
            #print(default[0])
            ret += "{}={},".format(_convert_(t.name), default[0])
            continue

        ret += "%s=," % _convert_(t.name)

    return ret.strip(',')


def get_inputs(op_type):
    ret = "inputs={"
    inputs = _get_inputs(op_type)
    for t in inputs:
        ret += "'{}': {},".format(t, _convert_(t))
    ret = ret.strip(",")
    ret += "}"

    if ret == "inputs={}":
        return ""

    return ret


def get_outputs(op_type):
    ret = "outputs={"
    inputs = _get_outputs(op_type)
    for t in inputs:
        ret += "'{}': {},".format(t, _convert_(t))
    ret = ret.strip(",")
    ret += "}"

    if ret == "inputs={}":
        return ""

    return ret


def get_attrs(op_type):
    ret = "attrs={"
    for t in _get_attrs(op_type):
        if t.name in g_filer_attrs:
            continue

        ret += "'%s': %s," % (t.name, _convert_(t.name))

    ret = ret.strip(",")
    ret += "}"

    return ret


def get_outvars(op_type, indent=1):
    inputs = _get_inputs(op_type)
    ret = ""
    for t in _get_outputs(op_type):
        ret += get_indent_space(
            indent
        ) + "%s = helper.create_tmp_variable(dtype=helper.input_dtype('%s'))\n" % (
            (_convert_(t), list(inputs)[0]))
    ret = ret.strip('\n')
    return ret


def get_op_py(op_type):
    input_comments = get_input_comments(op_type)
    output_comments = get_output_comments(op_type)
    args = get_func_args(op_type)
    inputs = get_inputs(op_type)
    outputs = get_outputs(op_type)
    attrs = get_attrs(op_type)
    out_vars = get_outvars(op_type)
    comment = get_comment(op_type)

    code = """
def {op_type}({args}):
    \"\"\"
    {comment}
    Args:
{input_comments}

    Returns:
{output_comments}
    \"\"\"
    
    helper = LayerHelper('{op_type}', **locals())
{generated_outvar}
    helper.append_op(
        type='{op_type}',
        {inputs},
        {outputs},
        {attrs})    
    
    return out
""".format(
        comment=comment,
        input_comments=input_comments.strip('\n'),
        output_comments=output_comments,
        args=args,
        generated_outvar=out_vars,
        op_type=op_type,
        inputs=inputs,
        outputs=outputs,
        attrs=attrs)

    return code


print(get_op_py("uniform_random_batch_size_like"))
#print(get_op_py("gaussian_random"))
#print(get_op_py("sampling_id"))
#print(get_op_py("gaussian_random_batch_size_like"))
#print(get_op_py("sum"))
#print(get_op_py("slice"))
#print(get_op_py("shape"))
#get_meta("linear_chain_crf")
