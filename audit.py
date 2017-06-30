import os
import csv
import glob
from collections import OrderedDict
import subprocess
import shutil
import utils
import logging

logger = logging.getLogger(__name__)


def generate_files_to_stage(conf_dict, annotations, seq_strategy):
    # audit path
    file_path = conf_dict.get('ega_audit').get('file_path')
    file_version = conf_dict.get('ega_audit').get('file_version')
    file_pattern = conf_dict.get('ega_audit').get('file_pattern')
    # output path
    output_path = conf_dict.get('ega_operation').get('file_path')
    to_stage_type = conf_dict.get('ega_operation').get('to_stage').get('type')
    mapping = conf_dict.get('ega_operation').get('to_stage').get('mapping')

    # generate the files need to be staged
    files = glob.glob(os.path.join(file_path, file_version, file_pattern))
    for fname in files:
        project_code = fname.split('/')[-2]
        output_file_path = os.path.join(output_path, project_code)
        if os.path.exists(output_file_path): shutil.rmtree(output_file_path)
        os.makedirs(output_file_path)

        for t in to_stage_type:
            output_file_name = conf_dict.get('ega_operation').get('to_stage').get(t).get('file_name')
            output_fields = conf_dict.get('ega_operation').get('to_stage').get(t).get('fields')
            key = conf_dict.get('ega_operation').get('to_stage').get(t).get('key')
            require = conf_dict.get('ega_operation').get('to_stage').get(t).get('require')

            ega_file = {}
            with open(fname) as f:
                reader = csv.DictReader(f, delimiter='\t')
                for l in reader:
                    if not l.get(require[1]): continue
                    if not l.get(key[1]): continue
                    if seq_strategy and not l.get('ICGC Submitted Sequencing Strategy') in seq_strategy: continue
                    if not ega_file.get(l.get(key[1])): ega_file[l.get(key[1])] = OrderedDict()
                    for field in output_fields:
                        if not ega_file[l.get(key[1])].get(field): ega_file[l.get(key[1])][field] = set()
                        ega_file[l.get(key[1])][field].add(l.get(mapping.get(field), None))

                ega_file_list = []
                for fid, fvalue in ega_file.iteritems():
                    # skip the files already staged on ASPERA
                    if fid in annotations.get('staged'): continue 
                    # skip the files already in job completed:
                    if fid in annotations.get('completed'): continue

                    # QC the data
                    # skip the file if encrypted md5 = unencrypted md5
                    if fvalue['file_md5sum'] == fvalue['encrypted_file_md5sum']: 
                        logger.warning('%s:%s has the same file_md5sum and encrypted_file_md5sum: %s', project_code, fid, fvalue['file_md5sum'])
                        continue
                    skip=False
                    for h in output_fields:
                        # skip the file if there is any id inconsistent
                        if not h in ['dataset_id'] and len(fvalue[h]) > 1:
                            logger.warning('%s has the id inconsistent: %s', fid, h) 
                            skip=True
                    if skip: continue

                    ega_file_list.append(fvalue)
            

            # write to the file
            if not ega_file_list: continue
            with open(os.path.join(output_file_path, output_file_name), 'w') as o:
                o.write('\t'.join(output_fields) + '\n')
                for l in ega_file_list:
                    line = utils.get_line(l)
                    o.write('\t'.join(line) + '\n')


def generate_files_to_remove(conf_dict, annotations):
    to_remove_file_name = os.path.join(conf_dict.get('ega_operation').get('file_path'), conf_dict.get('ega_operation').get('to_remove'))
    # generate the files to be removed
    with open(to_remove_file_name, 'w') as f:
        for fid in annotations.get('completed'):
            try:
                ret = subprocess.check_output(['grep', fid, 'dbox_content'])
                f.write(ret)
            except subprocess.CalledProcessError:
                continue      
