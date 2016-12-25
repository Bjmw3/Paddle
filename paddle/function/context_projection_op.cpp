/* Copyright (c) 2016 PaddlePaddle Authors. All Rights Reserve.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License. */

#include "context_projection_op.h"
#include "paddle/math/Matrix.h"
#include "paddle/math/Vector.h"

namespace paddle {

template <>
void ContextProjectionForward<DEVICE_TYPE_CPU>(Tensor& output,
                                               const Tensor& input,
                                               const Tensor& weight,
                                               const Tensor& sequence,
                                               size_t context_length,
                                               int context_start,
                                               size_t begin_pad,
                                               bool is_padding) {
  CHECK(output.getData() && input.getData() && sequence.getData());
  CHECK_EQ(output.dims_.size(), 2);
  CHECK_EQ(input.dims_.size(), 2);
  CHECK_EQ(weight.dims_.size(), 2);
  CHECK_EQ(sequence.dims_.size(), 1);

  auto out_mat = std::make_shared<CpuMatrix>(
      output.getData(), output.dims_[0], output.dims_[1]);
  const auto in_mat = std::make_shared<CpuMatrix>(
      input.getData(), input.dims_[0], input.dims_[1]);
  const auto weight_mat =
      !weight.getData()
          ? nullptr
          : std::make_shared<CpuMatrix>(
                weight.getData(), weight.dims_[0], input.dims_[1]);
  CpuIVector seq_vec(sequence.dims_[0],
                     reinterpret_cast<int*>(sequence.getData()));
  CHECK_EQ(out_mat->getWidth(), in_mat->getWidth() * context_length);

  const int* starts = seq_vec.getData();
  const size_t num_sequences = seq_vec.getSize() - 1;
  for (size_t i = 0; i < num_sequences; ++i) {
    for (size_t j = 0; j < context_length; ++j) {
      int begin = starts[i] + context_start + j;
      int end = starts[i + 1] + context_start + j;
      int dst_begin = starts[i];
      int dst_end = starts[i + 1];
      if (begin < starts[i]) {
        int64_t pad_size =
            std::min(starts[i] - begin, starts[i + 1] - starts[i]);
        MatrixPtr mat = out_mat->subMatrix(starts[i], pad_size);
        if (is_padding && weight_mat) {
          MatrixPtr sub = weight_mat->subMatrix(j, pad_size);
          mat->addAtOffset(*sub, j * in_mat->getWidth());
        }
        dst_begin = starts[i] + pad_size;
        begin = starts[i];
      }
      if (end > starts[i + 1]) {
        int64_t pad_size =
            std::min(end - starts[i + 1], starts[i + 1] - starts[i]);
        MatrixPtr mat = out_mat->subMatrix(starts[i + 1] - pad_size, pad_size);
        if (is_padding && weight_mat) {
          MatrixPtr sub = weight_mat->subMatrix(
              begin_pad + context_start + j - pad_size, pad_size);
          mat->addAtOffset(*sub, j * in_mat->getWidth());
        }
        dst_end = starts[i + 1] - pad_size;
        end = starts[i + 1];
      }
      if (end <= begin) continue;
      MatrixPtr src = in_mat->subMatrix(begin, end - begin);
      MatrixPtr dst = out_mat->subMatrix(dst_begin, dst_end - dst_begin);
      dst->addAtOffset(*src, j * in_mat->getWidth());
    }
  }
}

/**
 * \param inputs[0] input value.
 * \param inputs[1] input weight.
 * \param inputs[2] input sequence.
 * \param outputs[0] output value.
 */
template <DeviceType Device>
class ContextProjectionForwardFunc : public FunctionBase {
public:
  void init(const FuncConfig& config) override {
    context_length_ = config.get<size_t>("context_length");
    context_start_ = config.get<int>("context_start");
    begin_pad_ = config.get<size_t>("begin_pad");
    is_padding_ = config.get<bool>("is_padding");
  }

  void calc(const Arguments& inputs,
            const Arguments& outputs,
            const Arguments& inouts) override {
    CHECK_EQ(3, inputs.size());
    CHECK_EQ(1, outputs.size());
    CHECK_EQ(0, inouts.size());

    ContextProjectionForward<Device>((Tensor&)outputs[0],
                                     inputs[0],
                                     inputs[1],
                                     inputs[2],
                                     context_length_,
                                     context_start_,
                                     begin_pad_,
                                     is_padding_);
  }

private:
  size_t context_length_;
  int context_start_;
  size_t begin_pad_;
  bool is_padding_;
};

REGISTER_TYPED_FUNC(ContextProjectionForward,
                    CPU,
                    ContextProjectionForwardFunc);
#ifndef PADDLE_ONLY_CPU
REGISTER_TYPED_FUNC(ContextProjectionForward,
                    GPU,
                    ContextProjectionForwardFunc);
#endif
}  // namespace paddle
