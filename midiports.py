
import mido

print('Input ports:')
for item in mido.get_input_names():
    print("\t{}".format(item))
print('Output ports:')
for item in mido.get_output_names():
    print("\t{}".format(item))
